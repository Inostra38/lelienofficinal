"""Toute pharmacie naît avec un abonnement.

`HasPaidAccess` refuse une pharmacie sans `Subscription`. Faire reposer cette
création sur la seule vue d'inscription laissait un trou : une pharmacie créée
par le shell, l'admin Django, `createsuperuser`, un import ou une fixture de
test n'avait aucun abonnement — donc aucun accès aux modules payants, sans
raison commerciale.

Le signal garantit l'invariant quel que soit le chemin de création.
"""

from datetime import timedelta

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid='billing_create_subscription')
def create_trial_subscription(sender, instance, created, raw=False, **kwargs):
    if not created or raw:
        # raw=True : chargement de fixture, l'état est fourni tel quel.
        return

    from apps.billing.models import Subscription

    Subscription.objects.get_or_create(
        pharmacy=instance,
        defaults={
            'status': Subscription.Status.TRIALING,
            'trial_ends_at': timezone.now() + timedelta(days=Subscription.TRIAL_DAYS),
        },
    )
