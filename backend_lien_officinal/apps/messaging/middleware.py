"""
Middleware WebSocket — authentification JWT via query parameter.

Le token JWT est stocké dans localStorage (pas HttpOnly cookie),
donc on le passe en query param : ws://.../?token=<jwt>
"""
from urllib.parse import parse_qs

import jwt
from django.conf import settings
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from apps.team.models import Collaborator


@database_sync_to_async
def get_collaborator_from_token(token: str):
    """
    Décode le JWT et retourne le Collaborator correspondant, ou None.
    Même logique que _get_collaborator() dans views.py.
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
    Middleware WebSocket : lit le JWT depuis ?token=<jwt> dans l'URL,
    authentifie le collaborateur et l'attache à la scope.
    """
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        params = parse_qs(query_string)
        token_list = params.get('token', [])
        token = token_list[0] if token_list else None

        if token:
            scope['collaborator'] = await get_collaborator_from_token(token)
        else:
            scope['collaborator'] = None

        return await super().__call__(scope, receive, send)
