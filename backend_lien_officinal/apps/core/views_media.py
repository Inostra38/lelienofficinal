"""
Vue de service des fichiers media protégés par JWT.

En dev local : sert les fichiers depuis MEDIA_ROOT.
En prod (S3) : redirige vers une signed URL Scaleway.

Préfixes gérés :
  quality/attachments/  → ProcedureAttachment (vérifié via procedure.pharmacy)
  quality/images/       → ProcedureImage (vérifié via procedure.pharmacy)
  pharmacy_logos/       → Pharmacy.logo (vérifié via request.user)
  cards/                → accès libre (icônes publiques / fiches partenaires)
  messaging/            → accès libre (pièces jointes messagerie interne)
"""

import os
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from apps.admin_panel.authentication import AdminJWTAuthentication


def _check_quality_attachment(path: str, pharmacy) -> bool:
    from apps.quality.models import ProcedureAttachment
    return ProcedureAttachment.objects.filter(
        file=path,
        procedure__pharmacy=pharmacy,
    ).exists()


def _check_quality_image(path: str, pharmacy) -> bool:
    from apps.quality.models import ProcedureImage
    return ProcedureImage.objects.filter(
        image=path,
        procedure__pharmacy=pharmacy,
    ).exists()


def _check_pharmacy_logo(path: str, pharmacy) -> bool:
    return str(pharmacy.logo) == path if pharmacy.logo else False


@api_view(["GET"])
@authentication_classes([JWTAuthentication, AdminJWTAuthentication])
@permission_classes([IsAuthenticated])
def serve_protected_media(request, path):
    """
    GET /media/<path> — Sert un fichier media après vérification JWT + appartenance.
    """
    user = request.user

    # Admin : accès complet à tous les fichiers
    from apps.admin_panel.models import AdminUser
    is_admin = isinstance(user, AdminUser)

    if not is_admin:
        pharmacy = user

        if path.startswith("quality/attachments/"):
            if not _check_quality_attachment(path, pharmacy):
                raise Http404

        elif path.startswith("quality/images/"):
            if not _check_quality_image(path, pharmacy):
                raise Http404

        elif path.startswith("pharmacy_logos/"):
            if not _check_pharmacy_logo(path, pharmacy):
                raise Http404

    # Mode S3 : rediriger vers une signed URL
    if hasattr(settings, 'AWS_S3_ENDPOINT_URL'):
        if not default_storage.exists(path):
            raise Http404
        url = default_storage.url(path)
        return HttpResponseRedirect(url)

    # Mode local : servir le fichier depuis MEDIA_ROOT
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    if not os.path.abspath(full_path).startswith(os.path.abspath(settings.MEDIA_ROOT)):
        raise Http404
    if not os.path.isfile(full_path):
        raise Http404
    return FileResponse(open(full_path, "rb"))
