"""Affiche l'état complet de l'abonnement d'une pharmacie (diagnostic, lecture seule).

Affiche aussi les abonnements Stripe réels du Customer, pour repérer les
abonnements orphelins (créés côté Stripe mais jamais enregistrés en base
suite à une erreur serveur pendant la confirmation).

Exemple :
    manage.py inspect_subscription webmaster@lienofficinal.fr
"""

import stripe
from django.core.management.base import BaseCommand, CommandError

from apps.billing.models import Subscription
from apps.billing.stripe_service import StripeService  # noqa: F401 — configure stripe.api_key
from apps.core.models import Pharmacy


class Command(BaseCommand):
    help = "Affiche l'état d'abonnement d'une pharmacie (diagnostic)."

    def add_arguments(self, parser):
        parser.add_argument('email', help="Email de la pharmacie.")

    def handle(self, *args, **options):
        email = options['email']
        pharmacy = Pharmacy.objects.filter(email=email).first()
        if pharmacy is None:
            raise CommandError(f"Pharmacie « {email} » introuvable.")

        sub = Subscription.objects.filter(pharmacy=pharmacy).first()
        if sub is None:
            self.stdout.write(f"{email} : aucune Subscription.")
            return

        self.stdout.write(f"pharmacy_id={pharmacy.id}")
        self.stdout.write(f"status={sub.status}")
        self.stdout.write(f"plan={sub.plan}")
        self.stdout.write(f"stripe_customer_id={sub.stripe_customer_id}")
        self.stdout.write(f"stripe_subscription_id={sub.stripe_subscription_id}")
        self.stdout.write(f"trial_ends_at={sub.trial_ends_at}")
        self.stdout.write(f"current_period_end={sub.current_period_end}")
        self.stdout.write(f"past_due_since={sub.past_due_since}")
        self.stdout.write(f"suspended_at={sub.suspended_at}")
        self.stdout.write(f"cancel_at_period_end={sub.cancel_at_period_end}")
        self.stdout.write(f"is_access_allowed={sub.is_access_allowed}")
        self.stdout.write(f"access_denied_reason={sub.access_denied_reason}")

        if not sub.stripe_customer_id:
            return

        self.stdout.write("--- Abonnements Stripe du Customer ---")
        stripe_subs = stripe.Subscription.list(customer=sub.stripe_customer_id, limit=20)
        if not stripe_subs.data:
            self.stdout.write("(aucun)")
            return
        for s in stripe_subs.data:
            orphan = " ORPHELIN (absent de la base)" if s.id != sub.stripe_subscription_id else ""
            self.stdout.write(
                f"id={s.id} status={s.status} "
                f"trial_end={s.trial_end} "
                f"current_period_end={getattr(s, 'current_period_end', None)}"
                f"{orphan}"
            )
