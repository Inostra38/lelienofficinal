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
def send_email_change_task(self, old_email: str, new_email: str, token: str):
    """Envoie l'email de confirmation de changement d'adresse (async, retry x3)."""
    from apps.core.email import send_email_change_confirmation
    try:
        send_email_change_confirmation(old_email, new_email, token)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def send_sms_task(self, log_id: int, phone: str, message: str):
    """Envoie un SMS via OVH en arrière-plan et met à jour le log."""
    from django.db.models import F
    from apps.core.models import SMSLog
    from apps.core.services import OVHService

    try:
        log = SMSLog.objects.get(id=log_id)
    except SMSLog.DoesNotExist:
        return

    try:
        svc = OVHService()
        ovh_id = svc.send_raw(phone, message)
        SMSLog.objects.filter(pk=log_id).update(
            status=SMSLog.Status.SUCCESS,
            ovh_message_id=ovh_id or '',
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
