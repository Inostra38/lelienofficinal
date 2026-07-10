"""
Vue de service des fichiers media protégés par JWT.

En dev local : sert les fichiers depuis MEDIA_ROOT.
En prod (S3) : redirige vers une signed URL Scaleway.

Préfixes gérés :
  quality/attachments/  → ProcedureAttachment (vérifié via procedure.pharmacy)
  quality/images/       → ProcedureImage (vérifié via procedure.pharmacy)
  pharmacy_logos/       → Pharmacy.logo (vérifié via request.user)
  cards/                → OFFICIAL/PARTNER : partagés ; PRIVATE : réservé au propriétaire (M1)
  invoices/             → facture PDF réservée à la pharmacie propriétaire (Q06)
  (tout autre préfixe)  → refusé par défaut (M1 : deny-by-default)
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


def _check_invoice(path: str, pharmacy) -> bool:
    """Q06 : une facture PDF (invoices/{pharmacy_id}/...) n'est servie qu'à la
    pharmacie propriétaire. Sans ce contrôle, le préfixe invoices/ tombait dans
    le deny-by-default → téléchargement de facture cassé en storage local."""
    from apps.billing.models import Invoice
    return Invoice.objects.filter(pdf_storage_key=path, pharmacy=pharmacy).exists()


def _check_card_media(path: str, pharmacy) -> bool:
    """
    M1 : un fichier de carte n'est servi que s'il est public (OFFICIAL/PARTNER,
    ressources partagées entre toutes les pharmacies) ou s'il appartient à la
    pharmacie demandeuse (carte PRIVATE). Empêche l'accès cross-tenant aux
    icônes/fichiers de cartes privées d'autres pharmacies.
    """
    from apps.resources.models import ResourceCard, ResourceItem

    if path.startswith("cards/icons/"):
        card = ResourceCard.objects.filter(icon=path).only('type', 'owner_pharmacy').first()
        if not card:
            return False
        if card.type in ('OFFICIAL', 'PARTNER'):
            return True
        return card.owner_pharmacy_id == pharmacy.id

    if path.startswith("cards/files/"):
        item = (
            ResourceItem.objects
            .filter(file=path)
            .select_related('card')
            .only('owner', 'card__type')
            .first()
        )
        if not item:
            return False
        if item.card and item.card.type in ('OFFICIAL', 'PARTNER'):
            return True
        return item.owner_id == pharmacy.id

    return False


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

        # M1 : deny-by-default — chaque préfixe connu a son contrôle
        # d'appartenance ; tout préfixe non listé est refusé.
        if path.startswith("quality/attachments/"):
            allowed = _check_quality_attachment(path, pharmacy)
        elif path.startswith("quality/images/"):
            allowed = _check_quality_image(path, pharmacy)
        elif path.startswith("pharmacy_logos/"):
            allowed = _check_pharmacy_logo(path, pharmacy)
        elif path.startswith("cards/"):
            allowed = _check_card_media(path, pharmacy)
        elif path.startswith("invoices/"):
            allowed = _check_invoice(path, pharmacy)
        else:
            allowed = False

        if not allowed:
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
