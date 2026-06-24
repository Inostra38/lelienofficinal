import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Suspension impayé J+7                                               #
# ------------------------------------------------------------------ #

@shared_task(bind=True, max_retries=3)
def schedule_suspension(self, subscription_id: int):
    """
    Appelée 7 jours après invoice.payment_failed.
    Suspend l'accès si le statut est toujours past_due.
    """
    from apps.billing.models import Subscription
    try:
        sub = Subscription.objects.get(id=subscription_id)
    except Subscription.DoesNotExist:
        return

    if sub.status != Subscription.Status.PAST_DUE:
        # Paiement régularisé entre-temps
        return

    sub.status = Subscription.Status.SUSPENDED
    sub.suspended_at = timezone.now()
    sub.save(update_fields=['status', 'suspended_at', 'updated_at'])
    logger.info('Pharmacy %s suspendue pour impayé', sub.pharmacy_id)

    send_suspension_email.delay(sub.pharmacy_id)


# ------------------------------------------------------------------ #
# Email fin de trial J-5                                              #
# ------------------------------------------------------------------ #

@shared_task
def send_trial_ending_email(pharmacy_id: int):
    """Envoie l'email 'Votre essai se termine bientôt' via Mailgun."""
    from apps.billing.email_service import send_trial_ending_email as _send
    _send(_get_pharmacy(pharmacy_id))


# ------------------------------------------------------------------ #
# Email suspension                                                    #
# ------------------------------------------------------------------ #

@shared_task
def send_suspension_email(pharmacy_id: int):
    """Envoie l'email de notification de suspension via Mailgun."""
    from apps.billing.email_service import send_suspension_email as _send
    _send(_get_pharmacy(pharmacy_id))


# ------------------------------------------------------------------ #
# Email relance impayé                                               #
# ------------------------------------------------------------------ #

@shared_task
def send_payment_failed_email(pharmacy_id: int):
    """Envoie l'email de relance après échec de prélèvement SEPA."""
    from apps.billing.email_service import send_payment_failed_email as _send
    _send(_get_pharmacy(pharmacy_id))


# ------------------------------------------------------------------ #
# Crédit SMS                                                          #
# ------------------------------------------------------------------ #

@shared_task(bind=True, max_retries=3)
def credit_sms_balance(self, pharmacy_id: int, quantity: int,
                        payment_intent_id: str, amount_cents: int):
    """Crédite le solde SMS après paiement CB réussi.

    Le solde est porté par ``core.Pharmacy.sms_credits`` (décision Prompt 1,
    pas de modèle SmsCredit) ; on incrémente via ``F()`` pour rester atomique,
    cohérent avec ``apps/core/views_sms.py``, et on journalise le mouvement
    dans ``SmsCreditTransaction``.
    """
    from apps.core.models import Pharmacy
    from apps.billing.models import SmsCreditTransaction
    from django.db import transaction
    from django.db.models import F

    try:
        with transaction.atomic():
            # Idempotence : Stripe peut redélivrer payment_intent.succeeded.
            # On ne crédite pas deux fois le même PaymentIntent.
            already = SmsCreditTransaction.objects.filter(
                reason=SmsCreditTransaction.Reason.PURCHASE,
                note__contains=payment_intent_id,
            ).exists()
            if already:
                logger.info('credit_sms_balance: PI %s déjà traité, ignoré', payment_intent_id)
                return

            updated = Pharmacy.objects.filter(pk=pharmacy_id).update(
                sms_credits=F('sms_credits') + quantity
            )
            if not updated:
                logger.warning('credit_sms_balance: pharmacy %s introuvable', pharmacy_id)
                return

            SmsCreditTransaction.objects.create(
                pharmacy_id=pharmacy_id,
                delta=quantity,
                reason=SmsCreditTransaction.Reason.PURCHASE,
                note=f'Pack {quantity} SMS — PI {payment_intent_id}',
            )

        generate_sms_receipt.delay(
            pharmacy_id=pharmacy_id,
            payment_intent_id=payment_intent_id,
            amount_cents=amount_cents,
            quantity=quantity,
        )

    except Exception as exc:
        logger.exception('credit_sms_balance error: %s', exc)
        raise self.retry(exc=exc, countdown=60)


# ------------------------------------------------------------------ #
# Génération facture abonnement (WeasyPrint)                          #
# ------------------------------------------------------------------ #

def _get_pharmacy(pharmacy_id: int):
    """Récupère la pharmacie (core.Pharmacy = AbstractBaseUser)."""
    from apps.core.models import Pharmacy
    return Pharmacy.objects.get(id=pharmacy_id)


@shared_task(bind=True, max_retries=3)
def generate_subscription_invoice(self, pharmacy_id: int,
                                   stripe_invoice_id: str, amount_cents: int):
    """Génère la facture PDF abonnement (WeasyPrint) et la stocke."""
    from apps.billing.models import Invoice, Subscription
    from apps.billing.pdf_service import generate_subscription_invoice_pdf

    try:
        # Idempotence : Stripe peut redélivrer invoice.paid.
        if Invoice.objects.filter(stripe_invoice_id=stripe_invoice_id).exists():
            logger.info('Facture déjà générée pour %s, ignorée', stripe_invoice_id)
            return

        pharmacy = _get_pharmacy(pharmacy_id)
        sub      = Subscription.objects.get(pharmacy=pharmacy)

        invoice = Invoice.objects.create(
            pharmacy=pharmacy,
            invoice_type=Invoice.InvoiceType.SUBSCRIPTION,
            invoice_number=Invoice.generate_invoice_number('subscription'),
            stripe_invoice_id=stripe_invoice_id,
            amount_ht=0,      # recalculés dans pdf_service
            amount_ttc=0,
        )

        generate_subscription_invoice_pdf(
            invoice=invoice,
            pharmacy=pharmacy,
            amount_ttc_cents=amount_cents,
            period_start=sub.current_period_end,
            period_end=sub.current_period_end,
        )

        logger.info('Facture abonnement générée : %s', invoice.invoice_number)

        # Email avec PDF joint + lien de téléchargement signé
        from apps.billing.pdf_service import read_pdf_bytes, generate_signed_url
        from apps.billing.email_service import send_subscription_invoice_email
        send_subscription_invoice_email(
            pharmacy=pharmacy,
            invoice=invoice,
            pdf_bytes=read_pdf_bytes(invoice.pdf_storage_key),
            download_url=generate_signed_url(invoice.pdf_storage_key),
        )

    except Exception as exc:
        logger.exception('generate_subscription_invoice error: %s', exc)
        raise self.retry(exc=exc, countdown=120)


# ------------------------------------------------------------------ #
# Génération reçu SMS (WeasyPrint)                                    #
# ------------------------------------------------------------------ #

@shared_task(bind=True, max_retries=3)
def generate_sms_receipt(self, pharmacy_id: int, payment_intent_id: str,
                          amount_cents: int, quantity: int):
    """Génère le reçu PDF pack SMS (WeasyPrint) et le stocke."""
    from apps.billing.models import Invoice
    from apps.billing.pdf_service import generate_sms_receipt_pdf

    try:
        # Idempotence : Stripe peut redélivrer payment_intent.succeeded.
        if Invoice.objects.filter(stripe_payment_intent_id=payment_intent_id).exists():
            logger.info('Reçu déjà généré pour PI %s, ignoré', payment_intent_id)
            return

        pharmacy = _get_pharmacy(pharmacy_id)

        invoice = Invoice.objects.create(
            pharmacy=pharmacy,
            invoice_type=Invoice.InvoiceType.SMS_PACK,
            invoice_number=Invoice.generate_invoice_number('sms_pack'),
            stripe_payment_intent_id=payment_intent_id,
            amount_ht=0,
            amount_ttc=0,
        )

        generate_sms_receipt_pdf(
            invoice=invoice,
            pharmacy=pharmacy,
            amount_ttc_cents=amount_cents,
            sms_quantity=quantity,
        )

        logger.info('Reçu SMS généré : %s', invoice.invoice_number)

        # Email avec PDF joint + lien de téléchargement signé
        from apps.billing.pdf_service import read_pdf_bytes, generate_signed_url
        from apps.billing.email_service import send_sms_receipt_email
        send_sms_receipt_email(
            pharmacy=pharmacy,
            invoice=invoice,
            sms_quantity=quantity,
            pdf_bytes=read_pdf_bytes(invoice.pdf_storage_key),
            download_url=generate_signed_url(invoice.pdf_storage_key),
        )

    except Exception as exc:
        logger.exception('generate_sms_receipt error: %s', exc)
        raise self.retry(exc=exc, countdown=120)


# ------------------------------------------------------------------ #
# Tâche périodique : basculement de tranche (nightly)                 #
# ------------------------------------------------------------------ #

@shared_task
def check_plan_upgrades():
    """
    Tâche Celery Beat — exécutée chaque nuit à 2h00.
    Vérifie si des pharmacies ont changé de tranche (< 10 / ≥ 10 collaborateurs)
    et met à jour leur plan Stripe si nécessaire.
    """
    from apps.billing.models import Subscription
    from apps.billing.stripe_service import StripeService

    active_subs = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING]
    ).select_related('pharmacy')

    for sub in active_subs:
        try:
            # Compte les collaborateurs actifs de la pharmacie
            # (apps.team.Collaborator : related_name='collaborators', champ is_active)
            collab_count = sub.pharmacy.collaborators.filter(is_active=True).count()
            expected_plan = 'large' if collab_count >= 10 else 'small'

            if expected_plan != sub.plan:
                old_plan = sub.plan
                if sub.stripe_subscription_id:
                    StripeService.update_subscription_plan(
                        sub.stripe_subscription_id, expected_plan
                    )
                sub.plan = expected_plan
                sub.save(update_fields=['plan', 'updated_at'])
                logger.info(
                    'Plan mis à jour → pharmacy %s : %s → %s',
                    sub.pharmacy_id, old_plan, expected_plan
                )
        except Exception as exc:
            logger.exception('check_plan_upgrades error pharmacy %s: %s', sub.pharmacy_id, exc)
            continue
