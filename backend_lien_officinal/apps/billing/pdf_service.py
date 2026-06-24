import base64
import logging
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Constantes émetteur                                                 #
# ⚠️ LÉGALEMENT OBLIGATOIRE sur une facture française — À REMPLIR     #
#    avec les vraies données de Le Lien Officinal SAS avant prod.     #
# ------------------------------------------------------------------ #
EMETTEUR = {
    'adresse':   '1 rue de la Pharmacie, 75000 Paris',  # À REMPLIR
    'siret':     '000 000 000 00000',                    # À REMPLIR
    'tva_intra': 'FR00000000000',                        # À REMPLIR
    'email':     'contact@lienofficinal.fr',
    'capital':   '1000',                                 # À REMPLIR
    'rcs':       'Paris B 000 000 000',                  # À REMPLIR
}

LOGO_PATH = Path(settings.BASE_DIR) / 'apps' / 'billing' / 'static' / 'billing' / 'logo.png'


def _load_logo_base64() -> str | None:
    """Charge le logo en base64 pour l'inclure inline dans le PDF."""
    try:
        if LOGO_PATH.exists():
            with open(LOGO_PATH, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
    except Exception as exc:
        logger.warning('Logo billing introuvable : %s', exc)
    return None


def _format_pharmacy_address(pharmacy) -> str:
    """Compose l'adresse sur une ligne depuis address1/address2/postal_code/city."""
    bits = [
        pharmacy.address1,
        pharmacy.address2,
        ' '.join(b for b in [pharmacy.postal_code, pharmacy.city] if b),
    ]
    return ', '.join(b for b in bits if b)


def _compute_amounts(amount_ttc_cents: int, tva_rate: Decimal):
    """
    Calcule HT, TVA et TTC à partir du montant TTC en centimes.
    Retourne des Decimal arrondis à 2 décimales.
    """
    ttc = Decimal(amount_ttc_cents) / 100
    ht  = (ttc / (1 + tva_rate / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    tva = (ttc - ht).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return ht, tva, ttc


def _render_pdf(template_name: str, context: dict) -> bytes:
    """Rend un template HTML via WeasyPrint et retourne les bytes du PDF."""
    html_string = render_to_string(template_name, context)
    return HTML(string=html_string, base_url=None).write_pdf()


def _save_pdf(pdf_bytes: bytes, storage_key: str) -> str:
    """
    Sauvegarde le PDF via le storage par défaut (django-storages).
    Marche en dev (FileSystemStorage) comme en prod (Scaleway S3).
    Retourne la clé réellement utilisée par le storage.
    """
    # Si une version existe déjà (régénération), on la remplace.
    if default_storage.exists(storage_key):
        default_storage.delete(storage_key)
    return default_storage.save(storage_key, ContentFile(pdf_bytes))


def read_pdf_bytes(storage_key: str) -> bytes:
    """Relit les octets d'un PDF stocké (pour pièce jointe email)."""
    with default_storage.open(storage_key, 'rb') as f:
        return f.read()


def generate_signed_url(storage_key: str, expires_in: int = 600) -> str:
    """
    URL de téléchargement du PDF.
    En prod (Scaleway S3) : URL signée valable `expires_in` secondes.
    En dev (FileSystemStorage) : URL `/media/...` (le kwarg expire n'existe pas).
    """
    try:
        return default_storage.url(storage_key, expire=expires_in)  # S3Boto3Storage
    except TypeError:
        return default_storage.url(storage_key)  # FileSystemStorage


def _emetteur_context() -> dict:
    return {
        'emetteur_adresse':   EMETTEUR['adresse'],
        'emetteur_siret':     EMETTEUR['siret'],
        'emetteur_tva_intra': EMETTEUR['tva_intra'],
        'emetteur_email':     EMETTEUR['email'],
        'capital_social':     EMETTEUR['capital'],
        'rcs':                EMETTEUR['rcs'],
        'logo_base64':        _load_logo_base64(),
    }


def _pharmacy_context(pharmacy) -> dict:
    return {
        'pharmacy_name':    pharmacy.nom_officine,
        'pharmacy_adresse': _format_pharmacy_address(pharmacy),
        'pharmacy_siret':   pharmacy.siret or '',
        'pharmacy_email':   pharmacy.email,
    }


# ------------------------------------------------------------------ #
# API publique                                                         #
# ------------------------------------------------------------------ #

def generate_subscription_invoice_pdf(
    invoice,         # instance Invoice
    pharmacy,        # instance Pharmacy
    amount_ttc_cents: int,
    period_start,
    period_end,
    tva_rate: Decimal = Decimal('20.00'),
) -> str:
    """
    Génère la facture d'abonnement, la sauvegarde sur le storage.
    Met à jour les montants + pdf_storage_key + paid_at de l'Invoice.
    Retourne la storage_key.
    """
    ht, tva_amount, ttc = _compute_amounts(amount_ttc_cents, tva_rate)

    # Montants enregistrés AVANT le rendu PDF (qui peut prendre plusieurs secondes),
    # pour que la facture n'apparaisse jamais à 0 dans l'historique.
    invoice.amount_ht = ht
    invoice.amount_ttc = ttc
    invoice.tva_rate = tva_rate
    invoice.paid_at = timezone.now()
    invoice.save(update_fields=['amount_ht', 'amount_ttc', 'tva_rate', 'paid_at'])

    plan_labels = {'small': 'Small — < 10 collaborateurs', 'large': 'Large — ≥ 10 collaborateurs'}
    try:
        plan = pharmacy.subscription.plan
    except Exception:
        plan = 'small'

    context = {
        **_emetteur_context(),
        **_pharmacy_context(pharmacy),

        'doc_type':       'Facture',
        'invoice_number': invoice.invoice_number,
        'issued_at':      timezone.now().strftime('%d/%m/%Y'),
        'paid_at':        timezone.now(),

        'plan_label':   plan_labels.get(plan, 'Small'),
        'period_start': period_start.strftime('%d/%m/%Y') if period_start else '',
        'period_end':   period_end.strftime('%d/%m/%Y') if period_end else '',

        'amount_ht':  str(ht),
        'amount_tva': str(tva_amount),
        'amount_ttc': str(ttc),
        'tva_rate':   str(tva_rate),
    }

    pdf_bytes   = _render_pdf('billing/invoice_subscription.html', context)
    storage_key = _save_pdf(pdf_bytes, f'invoices/{pharmacy.id}/{invoice.invoice_number}.pdf')

    invoice.pdf_storage_key = storage_key
    invoice.save(update_fields=['pdf_storage_key'])

    return storage_key


def generate_sms_receipt_pdf(
    invoice,
    pharmacy,
    amount_ttc_cents: int,
    sms_quantity: int,
    tva_rate: Decimal = Decimal('20.00'),
) -> str:
    """
    Génère le reçu pack SMS, le sauvegarde sur le storage.
    Retourne la storage_key.
    """
    ht, tva_amount, ttc = _compute_amounts(amount_ttc_cents, tva_rate)

    # Montants enregistrés AVANT le rendu PDF (qui peut prendre plusieurs secondes),
    # pour que le reçu n'apparaisse jamais à 0 dans l'historique.
    invoice.amount_ht = ht
    invoice.amount_ttc = ttc
    invoice.tva_rate = tva_rate
    invoice.paid_at = timezone.now()
    invoice.save(update_fields=['amount_ht', 'amount_ttc', 'tva_rate', 'paid_at'])

    context = {
        **_emetteur_context(),
        **_pharmacy_context(pharmacy),

        'doc_type':       'Reçu',
        'invoice_number': invoice.invoice_number,
        'issued_at':      timezone.now().strftime('%d/%m/%Y'),
        'paid_at':        timezone.now(),

        'sms_quantity': sms_quantity,
        'amount_ht':    str(ht),
        'amount_tva':   str(tva_amount),
        'amount_ttc':   str(ttc),
        'tva_rate':     str(tva_rate),
    }

    pdf_bytes   = _render_pdf('billing/invoice_sms.html', context)
    storage_key = _save_pdf(pdf_bytes, f'invoices/{pharmacy.id}/{invoice.invoice_number}.pdf')

    invoice.pdf_storage_key = storage_key
    invoice.save(update_fields=['pdf_storage_key'])

    return storage_key
