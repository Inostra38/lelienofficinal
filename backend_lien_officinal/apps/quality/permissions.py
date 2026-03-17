from rest_framework.permissions import BasePermission


def _get_collaborator(request, pharmacy):
    """
    Retourne le Collaborator actif depuis le claim JWT, lié à la pharmacie donnée.
    Retourne None si aucun collaborateur n'est identifié dans le token.
    """
    token = request.auth
    if not token:
        return None
    collab_id = token.get('collaborator_id')
    if not collab_id:
        return None
    try:
        from apps.team.models import Collaborator
        return Collaborator.objects.get(
            id=int(collab_id),
            pharmacy=pharmacy,
            is_active=True,
        )
    except Exception:
        return None


class IsPharmacyTitulaire(BasePermission):
    """Accès réservé au titulaire de la pharmacie."""

    def has_permission(self, request, view):
        collaborator = _get_collaborator(request, request.user)
        if collaborator is None:
            return False
        return collaborator.role == 'Titulaire'


class CanManageProcedures(BasePermission):
    """Titulaire, ou adjoint avec can_manage_procedures=True."""

    def has_permission(self, request, view):
        collaborator = _get_collaborator(request, request.user)
        if collaborator is None:
            return False
        if collaborator.role == 'Titulaire':
            return True
        return collaborator.role == 'Adjoint' and collaborator.can_manage_procedures


class CanPublishProcedures(BasePermission):
    """Titulaire, ou adjoint avec can_publish_procedures=True."""

    def has_permission(self, request, view):
        collaborator = _get_collaborator(request, request.user)
        if collaborator is None:
            return False
        if collaborator.role == 'Titulaire':
            return True
        return collaborator.role == 'Adjoint' and collaborator.can_publish_procedures


class CanCloseNonConformities(BasePermission):
    """Titulaire, ou adjoint avec can_close_nonconformities=True."""

    def has_permission(self, request, view):
        collaborator = _get_collaborator(request, request.user)
        if collaborator is None:
            return False
        if collaborator.role == 'Titulaire':
            return True
        return collaborator.role == 'Adjoint' and collaborator.can_close_nonconformities


class IsProcedurePilot(BasePermission):
    """Vrai si le collaborateur connecté est le pilote de la procédure (permission objet)."""

    def has_permission(self, request, view):
        return True  # filtrage fin au niveau objet

    def has_object_permission(self, request, view, obj):
        collaborator = _get_collaborator(request, request.user)
        if collaborator is None:
            return False
        return obj.pilot_id == collaborator.id
