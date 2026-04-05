import jwt
from django.conf import settings
from django.core.cache import cache
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import AdminUser

_ALGORITHM = 'HS256'


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
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
        except jwt.PyJWTError:
            raise AuthenticationFailed('Token admin invalide ou expiré.')

        if payload.get('type') != 'admin':
            raise AuthenticationFailed('Token admin invalide.')

        # Vérifier blacklist (tokens révoqués au logout)
        jti = payload.get('jti')
        if jti and cache.get(f"admin_blacklist_{jti}"):
            raise AuthenticationFailed('Token révoqué.')

        try:
            admin = AdminUser.objects.get(pk=int(payload['sub']), is_active=True)
        except AdminUser.DoesNotExist:
            raise AuthenticationFailed('Admin introuvable.')

        return (admin, token)
