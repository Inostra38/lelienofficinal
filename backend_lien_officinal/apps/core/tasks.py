from celery import shared_task


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
