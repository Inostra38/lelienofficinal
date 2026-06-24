import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email_task(self, email: str, token: str):
    """Envoie l'email de vérification de compte via Mailgun (async, retry x3)."""
    from apps.core.email import send_verification_email
    try:
        send_verification_email(email, token)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_task(self, email: str, token: str):
    """Envoie l'email de réinitialisation de mot de passe (async, retry x3)."""
    from apps.core.email import send_password_reset_email
    try:
        send_password_reset_email(email, token)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_change_task(self, old_email: str, new_email: str, token: str):
    """Envoie l'email de confirmation de changement d'adresse (async, retry x3)."""
    from apps.core.email import send_email_change_confirmation
    try:
        send_email_change_confirmation(old_email, new_email, token)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def send_sms_task(self, log_id: int, phone: str, message: str):
    """Envoie un SMS via SMS Partner en arrière-plan et met à jour le log."""
    from django.db.models import F
    from apps.core.models import SMSLog
    from apps.core.services import SMSPartnerService

    try:
        log = SMSLog.objects.get(id=log_id)
    except SMSLog.DoesNotExist:
        return

    try:
        svc = SMSPartnerService()
        provider_id = svc.send_raw(phone, message)
        SMSLog.objects.filter(pk=log_id).update(
            status=SMSLog.Status.SUCCESS,
            provider_message_id=provider_id or '',
        )
    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            # Échec définitif : marquer et rembourser les crédits
            SMSLog.objects.filter(pk=log_id).update(
                status=SMSLog.Status.FAILED,
                error_message=str(exc),
            )
            from apps.core.models import Pharmacy
            Pharmacy.objects.filter(pk=log.pharmacy_id).update(
                sms_credits=F('sms_credits') + log.credits_used
            )


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def execute_account_deletion_task(self, pharmacy_id: int):
    """Exécute l'anonymisation d'un compte (déclenchée par le webhook Stripe à
    la fin de la période, pour une exécution immédiate)."""
    from apps.core.account_deletion import execute_account_deletion
    try:
        execute_account_deletion(pharmacy_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(name='apps.core.tasks.execute_scheduled_deletions')
def execute_scheduled_deletions():
    """Balayage quotidien : anonymise les comptes dont la suppression est échue.

    Filet de sécurité (le webhook Stripe déclenche l'exécution immédiate en fin
    de période ; ce balayage couvre les comptes sans abonnement — délai 30 j —
    et les éventuels webhooks manqués).
    """
    from django.utils import timezone
    from apps.core.models import Pharmacy
    from apps.core.account_deletion import execute_account_deletion

    due_ids = list(
        Pharmacy.objects.filter(
            deletion_scheduled_for__isnull=False,
            deletion_scheduled_for__lte=timezone.now(),
            anonymized_at__isnull=True,
        ).values_list('id', flat=True)
    )
    count = 0
    for pid in due_ids:
        try:
            if execute_account_deletion(pid):
                count += 1
        except Exception:
            logger.exception("[Account Deletion Sweep] échec pharmacy_id=%s", pid)
    logger.info("[Account Deletion Sweep] %s compte(s) anonymisé(s)", count)
    return count


@shared_task(name='sms.cleanup_old_sms_logs')
def cleanup_old_sms_logs():
    """
    Supprime les SMSLog de plus de 30 jours.
    TTL RGPD : rétention maximale 30 jours.
    """
    from datetime import timedelta
    from django.utils import timezone
    from apps.core.models import SMSLog

    cutoff = timezone.now() - timedelta(days=30)
    deleted_count, _ = SMSLog.objects.filter(sent_at__lt=cutoff).delete()
    logger.info(f"[SMS Cleanup] {deleted_count} logs supprimés (antérieurs au {cutoff.date()})")
    return deleted_count
