import jwt
from django.conf import settings
from django.core.cache import caches
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import AdminUser

_ALGORITHM = 'HS256'


def is_jti_revoked(jti) -> bool:
    """Vrai si le jti est blacklisté, OU si Redis est injoignable (fail-closed).

    S21 : la blacklist vit dans le cache `admin_revocation` (Redis natif, qui
    LÈVE sur erreur), pas dans le `default` résilient qui renverrait None sur un
    hoquet Redis — auquel cas un token révoqué serait accepté. On ne peut pas
    prouver qu'un token n'est PAS révoqué si Redis est muet → on refuse.
    """
    if not jti:
        return False
    try:
        return bool(caches['admin_revocation'].get(f"admin_blacklist_{jti}"))
    except Exception:
        return True


class AdminJWTAuthentication(BaseAuthentication):
    """
    Authentification DRF pour les endpoints admin.
    Lit le token depuis le header Authorization: Bearer <token>.
    Vérifie que le payload contient type='admin'.
    Vérifie que le jti n'est pas blacklisté (logout).
    """

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, settings.ADMIN_JWT_SECRET, algorithms=[_ALGORITHM])  # E1 : clé admin dédiée
        except jwt.PyJWTError:
            raise AuthenticationFailed('Token admin invalide ou expiré.')

        if payload.get('type') != 'admin':
            raise AuthenticationFailed('Token admin invalide.')

        # Vérifier blacklist (tokens révoqués au logout) — fail-closed (S21)
        if is_jti_revoked(payload.get('jti')):
            raise AuthenticationFailed('Token révoqué.')

        try:
            admin = AdminUser.objects.get(pk=int(payload['sub']), is_active=True)
        except AdminUser.DoesNotExist:
            raise AuthenticationFailed('Admin introuvable.')

        return (admin, token)
