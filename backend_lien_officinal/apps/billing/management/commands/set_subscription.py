"""Force l'état d'abonnement d'une pharmacie.

Sert à deux choses :
  1. Régulariser les comptes antérieurs à la mise en place de l'offre freemium
     (2026-07-19), qui n'ont aucun objet Subscription et se verraient refuser
     les modules payants.
  2. Basculer un compte de test d'un état à l'autre pour vérifier le
     comportement de l'application (essai en cours, essai expiré, impayé,
     suspendu…) sans passer par Stripe.

Exemples :
    manage.py set_subscription webmaster@lelienofficinal.fr --status active
    manage.py set_subscription webmaster@lelienofficinal.fr --status trialing --trial-days 30
    manage.py set_subscription webmaster@lelienofficinal.fr --status trialing --trial-days -1  # essai expiré
    manage.py set_subscription webmaster@lelienofficinal.fr --status past_due --past-due-days 8
    manage.py set_subscription --all-missing --status active   # régularisation de masse
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.billing.models import Subscription
from apps.core.models import Pharmacy


class Command(BaseCommand):
    help = "Force le statut d'abonnement d'une pharmacie (tests et régularisation)."

    def add_arguments(self, parser):
        parser.add_argument('email', nargs='?', help="Email de la pharmacie.")
        parser.add_argument(
            '--all-missing', action='store_true',
            help="Traiter toutes les pharmacies dépourvues d'abonnement.",
        )
        parser.add_argument(
            '--status', default=Subscription.Status.ACTIVE,
            choices=[s.value for s in Subscription.Status],
        )
        parser.add_argument(
            '--trial-days', type=int, default=Subscription.TRIAL_DAYS,
            help="Jours restants d'essai. Négatif = essai déjà expiré.",
        )
        parser.add_argument(
            '--past-due-days', type=int, default=0,
            help="Ancienneté de l'impayé en jours. Au-delà de 7, l'accès est coupé.",
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        email = options['email']
        all_missing = options['all_missing']

        if not email and not all_missing:
            raise CommandError("Fournir un email, ou --all-missing.")

        if all_missing:
            targets = [p for p in Pharmacy.objects.all()
                       if not Subscription.objects.filter(pharmacy=p).exists()]
            if not targets:
                self.stdout.write("Aucune pharmacie sans abonnement.")
                return
        else:
            pharmacy = Pharmacy.objects.filter(email=email).first()
            if pharmacy is None:
                known = ', '.join(Pharmacy.objects.values_list('email', flat=True)[:10])
                raise CommandError(f"Pharmacie « {email} » introuvable. Connues : {known}")
            targets = [pharmacy]

        for pharmacy in targets:
            self._apply(pharmacy, options)

    def _apply(self, pharmacy, options):
        status = options['status']
        now = timezone.now()

        subscription, created = Subscription.objects.get_or_create(pharmacy=pharmacy)
        subscription.status = status

        # Les dates gouvernent l'accès (cf. Subscription.is_access_allowed) :
        # les positionner explicitement, sinon un statut seul ne suffit pas.
        if status == Subscription.Status.TRIALING:
            subscription.trial_ends_at = now + timedelta(days=options['trial_days'])
            subscription.past_due_since = None
            subscription.suspended_at = None
        elif status == Subscription.Status.PAST_DUE:
            subscription.past_due_since = now - timedelta(days=options['past_due_days'])
            subscription.suspended_at = None
        elif status == Subscription.Status.SUSPENDED:
            subscription.suspended_at = now
        else:  # ACTIVE, CANCELED
            subscription.past_due_since = None
            subscription.suspended_at = None

        if options['dry_run']:
            self.stdout.write(
                f"[simulation] {pharmacy.email} → {status} "
                f"(accès payant : {subscription.is_access_allowed})"
            )
            return

        subscription.save()
        verb = 'créé' if created else 'mis à jour'
        access = 'ouvert' if subscription.is_access_allowed else 'REFUSÉ'
        self.stdout.write(self.style.SUCCESS(
            f"{pharmacy.email} : abonnement {verb} → {status} — accès payant {access}"
        ))
