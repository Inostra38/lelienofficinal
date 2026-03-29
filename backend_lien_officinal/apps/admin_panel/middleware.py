from django.conf import settings
from django.http import HttpResponse


class AdminIPWhitelistMiddleware:
    """
    Bloque toutes les requêtes vers /api/admin/* dont l'IP source
    n'est pas dans ADMIN_ALLOWED_IPS.
    Renvoie HTTP 403 sans message explicite.
    Lit l'IP depuis HTTP_X_FORWARDED_FOR en premier (Scalingo proxy),
    sinon REMOTE_ADDR.
    """
    ADMIN_PREFIX = '/api/admin/'

    def __init__(self, get_response):
        self.get_response = get_response
        raw = settings.ADMIN_ALLOWED_IPS  # "x.x.x.x,y.y.y.y"
        self.allowed = set(ip.strip() for ip in raw.split(',') if ip.strip())

    def __call__(self, request):
        if request.path.startswith(self.ADMIN_PREFIX):
            ip = self._get_ip(request)
            if ip not in self.allowed:
                return HttpResponse(status=403)
        return self.get_response(request)

    def _get_ip(self, request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
