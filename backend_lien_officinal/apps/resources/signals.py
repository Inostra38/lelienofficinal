import requests
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone

from .models import ResourceCard, ResourceItem


def _send_recommendation_email(instance_type: str, title: str, pharmacy_name: str):
    """Envoie un email de notification quand une recommandation est soumise."""
    admin_url = "https://lienofficinal.fr/admin/recommandations"

    try:
        requests.post(
            f"https://api.eu.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
            auth=("api", settings.MAILGUN_API_KEY),
            data={
                "from": f"Le Lien Officinal <noreply@{settings.MAILGUN_DOMAIN}>",
                "to": settings.ADMIN_NOTIFICATION_EMAIL,
                "subject": f"[Le Lien Officinal] Nouvelle recommandation : {title}",
                "text": (
                    f"Une pharmacie a recommand\u00e9 une ressource \u00e0 la communaut\u00e9.\n\n"
                    f"Type : {instance_type}\n"
                    f"Titre : {title}\n"
                    f"Pharmacie : {pharmacy_name}\n\n"
                    f"Acc\u00e9der au panel admin pour valider :\n{admin_url}"
                ),
            },
        )
    except Exception:
        pass  # fail silently


@receiver(pre_save, sender=ResourceCard)
def on_card_recommendation(sender, instance, **kwargs):
    """Detecte le passage de recommended_to_community a True."""
    if not instance.pk:
        return
    try:
        old = ResourceCard.objects.get(pk=instance.pk)
    except ResourceCard.DoesNotExist:
        return

    if not old.recommended_to_community and instance.recommended_to_community:
        instance.recommended_at = timezone.now()
        instance.recommendation_status = 'PENDING'
        pharmacy_name = str(instance.owner_pharmacy) if instance.owner_pharmacy else 'Inconnue'
        _send_recommendation_email('Carte', instance.titre, pharmacy_name)


@receiver(pre_save, sender=ResourceItem)
def on_item_recommendation(sender, instance, **kwargs):
    """Detecte le passage de recommended_to_community a True."""
    if not instance.pk:
        return
    try:
        old = ResourceItem.objects.get(pk=instance.pk)
    except ResourceItem.DoesNotExist:
        return

    if not old.recommended_to_community and instance.recommended_to_community:
        instance.recommended_at = timezone.now()
        instance.recommendation_status = 'PENDING'
        title = instance.label or str(instance.card)
        pharmacy_name = str(instance.card.owner_pharmacy) if instance.card.owner_pharmacy else 'Inconnue'
        _send_recommendation_email('Lien', title, pharmacy_name)
