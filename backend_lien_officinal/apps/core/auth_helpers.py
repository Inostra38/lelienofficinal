"""
Helpers d'authentification partagés entre tous les modules.
Centralise l'extraction du collaborateur depuis le JWT.
"""
from apps.team.models import Collaborator


def get_collaborator_from_jwt(request):
    """
    Extrait le collaborateur authentifié depuis le JWT de la requête.
    Retourne None si :
    - pas de token
    - auth_type != 'collaborator'
    - collaborateur introuvable ou inactif
    - pharmacie ne correspond pas à request.user

    Usage :
        collaborator = get_collaborator_from_jwt(request)
        if collaborator is None:
            return Response(..., status=400)
    """
    token = request.auth
    if not token:
        return None
    if token.get('auth_type') != 'collaborator':
        return None
    collab_id = token.get('collaborator_id')
    if not collab_id:
        return None
    try:
        return Collaborator.objects.get(
            id=int(collab_id),
            pharmacy=request.user,
            is_active=True,
        )
    except (Collaborator.DoesNotExist, ValueError):
        return None
