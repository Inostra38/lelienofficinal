"""
Middleware WebSocket — authentification JWT via sous-protocole.

Le token JWT est passé comme sous-protocole WebSocket au lieu
de l'URL query string, pour éviter l'exposition dans les logs serveur.
"""
import jwt
from django.conf import settings
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from apps.team.models import Collaborator


@database_sync_to_async
def get_collaborator_from_token(token: str):
    """
    Décode le JWT et retourne le Collaborator correspondant, ou None.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        if payload.get('auth_type') != 'collaborator':
            return None
        collaborator_id = payload.get('collaborator_id')
        if not collaborator_id:
            return None
        return Collaborator.objects.select_related('pharmacy').get(
            id=int(collaborator_id), is_active=True
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Collaborator.DoesNotExist, ValueError):
        return None


class JWTAuthMiddleware(BaseMiddleware):
    """
    Middleware WebSocket : lit le JWT depuis le sous-protocole.
    Le client envoie : new WebSocket(url, ['bearer', '<token>'])
    """
    async def __call__(self, scope, receive, send):
        subprotocols = scope.get('subprotocols', [])
        token = None

        # Le client envoie ['bearer', '<jwt>'] comme sous-protocoles
        if len(subprotocols) >= 2 and subprotocols[0] == 'bearer':
            token = subprotocols[1]

        if token:
            scope['collaborator'] = await get_collaborator_from_token(token)
        else:
            scope['collaborator'] = None

        return await super().__call__(scope, receive, send)
