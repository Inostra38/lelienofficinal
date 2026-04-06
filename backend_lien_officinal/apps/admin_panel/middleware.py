import jwt

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

from .models import AdminUser


class AdminIPWhitelistMiddleware:
    """
    Bloque toutes les requêtes vers /api/admin/* dont l'IP source
    n'est pas dans ADMIN_ALLOWED_IPS.
    Renvoie HTTP 403 sans message explicite.
    Lit l'IP depuis HTTP_X_FORWARDED_FOR en premier (Scalingo proxy),
    sinon REMOTE_ADDR.
    """
    PROTECTED_PREFIXES = ('/api/admin/', '/admin/')

    def __init__(self, get_response):
        self.get_response = get_response
        raw = settings.ADMIN_ALLOWED_IPS  # "x.x.x.x,y.y.y.y"
        self.allowed = set(ip.strip() for ip in raw.split(',') if ip.strip())

    def __call__(self, request):
        if any(request.path.startswith(p) for p in self.PROTECTED_PREFIXES):
            ip = self._get_ip(request)
            if ip not in self.allowed:
                return HttpResponse(status=403)
        return self.get_response(request)

    def _get_ip(self, request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


class AdminRateLimitMiddleware:
    """
    Rate limiting par IP sur les endpoints admin sensibles.
    Indépendant de DRF — s'applique même sans cookie/session.
    Désactivé en DEBUG pour le développement.
    """
    RATE_LIMITS = {
        'auth/login/': ('admin_rl_login', 20, 900),      # 20 req / 15 min
        'auth/totp-verify/': ('admin_rl_totp', 30, 900),  # 30 req / 15 min
    }
    ADMIN_PREFIX = '/api/admin/'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG:
            return self.get_response(request)

        if not request.path.startswith(self.ADMIN_PREFIX) or request.method != 'POST':
            return self.get_response(request)

        relative = request.path[len(self.ADMIN_PREFIX):]
        for endpoint, (prefix, max_hits, window) in self.RATE_LIMITS.items():
            if relative == endpoint:
                ip = self._get_ip(request)
                key = f"{prefix}_{ip}"
                hits = cache.get(key, 0)
                if hits >= max_hits:
                    return JsonResponse(
                        {'detail': 'Trop de tentatives. Réessayez plus tard.'},
                        status=429,
                    )
                cache.set(key, hits + 1, timeout=window)
                break

        return self.get_response(request)

    def _get_ip(self, request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


class AdminAccountGuardMiddleware:
    """
    Bloque les requêtes admin si le compte n'est pas entièrement configuré :
      - force_password_change == True → 403 password_change_required
      - totp_secret == '' → 403 totp_setup_required
    Les endpoints d'auth sont toujours autorisés.
    """
    ADMIN_PREFIX = '/api/admin/'
    AUTH_WHITELIST = (
        'auth/login/',
        'auth/totp-verify/',
        'auth/refresh/',
        'auth/logout/',
        'auth/totp-setup/',
        'auth/totp-setup/confirm/',
        'auth/change-password/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not path.startswith(self.ADMIN_PREFIX):
            return self.get_response(request)

        # Vérifier si l'endpoint est dans la whitelist
        relative = path[len(self.ADMIN_PREFIX):]
        if any(relative.startswith(ep) for ep in self.AUTH_WHITELIST):
            return self.get_response(request)

        # Résoudre l'admin depuis le JWT
        admin = self._resolve_admin(request)
        if admin is None:
            # Pas de token valide → laisser passer, les vues gèrent le 401
            return self.get_response(request)

        if admin.force_password_change:
            return JsonResponse(
                {'detail': 'Changement de mot de passe requis', 'code': 'password_change_required'},
                status=403,
            )

        if not admin.totp_secret:
            return JsonResponse(
                {'detail': 'Configuration TOTP requise', 'code': 'totp_setup_required'},
                status=403,
            )

        return self.get_response(request)

    def _resolve_admin(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None
        token = auth_header.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            if payload.get('type') != 'admin':
                return None
            return AdminUser.objects.get(pk=int(payload['sub']), is_active=True)
        except Exception:
            return None
