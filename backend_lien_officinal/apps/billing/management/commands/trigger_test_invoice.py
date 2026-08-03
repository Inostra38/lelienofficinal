"""Déclenche une facture hors-cycle sur l'abonnement Stripe d'une pharmacie.

Sert à tester le circuit de facturation récurrente (prélèvement SEPA →
webhook invoice.paid → génération PDF) sans attendre la prochaine échéance
naturelle de l'abonnement. Usage réservé au mode test Stripe.

Exemple :
    manage.py trigger_test_invoice webmaster@lienofficinal.fr
"""

import stripe
from django.core.management.base import BaseCommand, CommandError

from apps.billing.models import Subscription
from apps.billing.stripe_service import StripeService  # noqa: F401 — configure stripe.api_key
from apps.core.models import Pharmacy


class Command(BaseCommand):
    help = "Déclenche une facture hors-cycle pour tester le circuit de facturation récurrente."

    def add_arguments(self, parser):
        parser.add_argument('email', help="Email de la pharmacie.")

    def handle(self, *args, **options):
        email = options['email']
        pharmacy = Pharmacy.objects.filter(email=email).first()
        if pharmacy is None:
            raise CommandError(f"Pharmacie « {email} » introuvable.")

        sub = Subscription.objects.filter(pharmacy=pharmacy).first()
        if sub is None or not sub.stripe_subscription_id:
            raise CommandError("Aucun abonnement Stripe actif pour cette pharmacie.")

        # Invoice.create(subscription=...) seul ne récupère PAS le prix
        # récurrent du plan (uniquement les invoice items en attente) → facture
        # à 0 €. Pour tester un vrai cycle, on avance l'ancrage de facturation
        # à maintenant : Stripe clôt la période en cours et émet la facture
        # complète (prix du plan) pour la période suivante, avec prélèvement
        # SEPA immédiat — le comportement réel d'un renouvellement mensuel.
        subscription = stripe.Subscription.modify(
            sub.stripe_subscription_id,
            billing_cycle_anchor='now',
            proration_behavior='none',
        )

        self.stdout.write(self.style.SUCCESS(
            f"Cycle de facturation avancé sur {subscription.id} — "
            f"la facture du nouveau cycle va être émise et prélevée sous peu."
        ))
        self.stdout.write(
            "Le prélèvement SEPA est asynchrone : le paiement passera en "
            "'processing' puis 'paid' via webhook dans les minutes à venir."
        )
