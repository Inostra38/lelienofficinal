"""Annule IMMÉDIATEMENT un abonnement Stripe par son ID (pas de fin de période).

Sert à nettoyer les abonnements orphelins (créés côté Stripe mais jamais
rattachés en base suite à une erreur serveur pendant la confirmation) —
voir inspect_subscription pour les repérer.

Exemple :
    manage.py cancel_stripe_subscription sub_1U0KklF34Y6hMuLfaZAPQKdX
"""

import stripe
from django.core.management.base import BaseCommand, CommandError

from apps.billing.stripe_service import StripeService  # noqa: F401 — configure stripe.api_key


class Command(BaseCommand):
    help = "Annule immédiatement un abonnement Stripe par son ID (nettoyage orphelin)."

    def add_arguments(self, parser):
        parser.add_argument('subscription_id', help="ID Stripe (sub_...).")

    def handle(self, *args, **options):
        sub_id = options['subscription_id']
        try:
            canceled = stripe.Subscription.delete(sub_id)
        except stripe.InvalidRequestError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(
            f"{sub_id} annulé — status={canceled.status}"
        ))
