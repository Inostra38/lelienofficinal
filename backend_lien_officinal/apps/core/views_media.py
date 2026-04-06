"""
Vue de service des fichiers media protégés par JWT.

Toutes les requêtes /media/<path> passent par cette vue.
L'appartenance est vérifiée par lookup en base selon le préfixe du chemin.

Préfixes gérés :
  quality/attachments/  → ProcedureAttachment (vérifié via procedure.pharmacy)
  quality/images/       → ProcedureImage (vérifié via procedure.pharmacy)
  pharmacy_logos/       → Pharmacy.logo (vérifié via request.user)
  cards/                → accès libre (icônes publiques / fiches partenaires)
  messaging/            → accès libre (pièces jointes messagerie interne)
"""

import os
from django.http import FileResponse, Http404
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from apps.admin_panel.authentication import AdminJWTAuthentication


def _resolve_path(path: str):
    """Retourne le chemin absolu validé, ou lève Http404 en cas de path traversal."""
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    if not os.path.abspath(full_path).startswith(os.path.abspath(settings.MEDIA_ROOT)):
        raise Http404
    if not os.path.isfile(full_path):
        raise Http404
    return full_path


def _check_quality_attachment(path: str, pharmacy) -> bool:
    """Vérifie que la pièce jointe appartient à la pharmacie de l'utilisateur."""
    from apps.quality.models import ProcedureAttachment
    return ProcedureAttachment.objects.filter(
        file=path,
        procedure__pharmacy=pharmacy,
    ).exists()


def _check_quality_image(path: str, pharmacy) -> bool:
    """Vérifie que l'image appartient à la pharmacie de l'utilisateur."""
    from apps.quality.models import ProcedureImage
    return ProcedureImage.objects.filter(
        image=path,
        procedure__pharmacy=pharmacy,
    ).exists()


def _check_pharmacy_logo(path: str, pharmacy) -> bool:
    """Vérifie que le logo appartient à la pharmacie de l'utilisateur."""
    return str(pharmacy.logo) == path if pharmacy.logo else False


@api_view(["GET"])
@authentication_classes([JWTAuthentication, AdminJWTAuthentication])
@permission_classes([IsAuthenticated])
def serve_protected_media(request, path):
    """
    GET /media/<path> — Sert un fichier media après vérification JWT + appartenance.
    """
    full_path = _resolve_path(path)
    user = request.user

    # Admin : accès complet à tous les fichiers (pas de vérification d'appartenance)
    from apps.admin_panel.models import AdminUser
    is_admin = isinstance(user, AdminUser)

    if not is_admin:
        pharmacy = user

        # Pièces jointes procédures (PDF, documents)
        if path.startswith("quality/attachments/"):
            if not _check_quality_attachment(path, pharmacy):
                raise Http404

        # Images procédures
        elif path.startswith("quality/images/"):
            if not _check_quality_image(path, pharmacy):
                raise Http404

        # Logo pharmacie
        elif path.startswith("pharmacy_logos/"):
            if not _check_pharmacy_logo(path, pharmacy):
                raise Http404

        # cards/ et messaging/ : ressources semi-publiques dans le contexte SaaS
        # Authentification JWT suffisante — pas de vérification d'appartenance stricte

    return FileResponse(open(full_path, "rb"))
