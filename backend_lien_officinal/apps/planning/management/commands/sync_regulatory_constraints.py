"""
Management command : synchronise les contraintes réglementaires CCN Pharmacie.

Aligne les contraintes réglementaires DB avec les règles compilées dans le
system prompt de l'IA (GenerateTemplateView) :
  - Supprime les contraintes de majoration salariale (hors scope planning)
  - Ajoute la règle de pause si absente
  - Met à jour les descriptions obsolètes

Usage :
    python manage.py sync_regulatory_constraints
    python manage.py sync_regulatory_constraints --pharmacy 2   # une seule officine
    python manage.py sync_regulatory_constraints --dry-run      # aperçu sans modification
"""
from django.core.management.base import BaseCommand

from apps.core.models import Pharmacy
from apps.planning.models import Constraint, ConstraintSet


# ── Référentiel cible ─────────────────────────────────────────────────────────

REGULATORY_TARGET = [
    (0,  'Repos quotidien minimum de 11 heures entre deux shifts'),
    (1,  'Amplitude journalière maximale de 12 heures'),
    (2,  'Durée de travail effectif maximale de 10 heures par jour'),
    (3,  'Pause de 20 minutes minimum obligatoire dès 6 heures de travail consécutif'),
    (4,  'Repos hebdomadaire de 35 heures consécutives minimum'),
    (5,  'Maximum 48 heures de travail par semaine'),
    (6,  'Maximum 44 heures de travail en moyenne sur 12 semaines consécutives'),
]

# Fragments permettant d'identifier les contraintes à supprimer
PATTERNS_TO_REMOVE = [
    'ajoration',        # Majoration / majoration
    'upplémentaire',    # Heures supplémentaires
]


def _should_remove(description: str) -> bool:
    return any(p in description for p in PATTERNS_TO_REMOVE)


class Command(BaseCommand):
    help = 'Synchronise les contraintes réglementaires CCN avec le référentiel courant'

    def add_arguments(self, parser):
        parser.add_argument('--pharmacy', type=int, default=None,
                            help='ID de la pharmacie (toutes par défaut)')
        parser.add_argument('--dry-run', action='store_true',
                            help='Affiche les changements sans les appliquer')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('Mode dry-run — aucune modification appliquée\n'))

        pharmacies = (
            Pharmacy.objects.filter(pk=options['pharmacy'])
            if options['pharmacy']
            else Pharmacy.objects.all()
        )

        for pharmacy in pharmacies:
            self.stdout.write(f'\n📋 {pharmacy.nom_officine} (id={pharmacy.pk})')
            constraint_set, _ = ConstraintSet.objects.get_or_create(pharmacy=pharmacy)
            self._sync(constraint_set, dry_run)

        self.stdout.write(self.style.SUCCESS('\nTerminé.'))

    def _sync(self, constraint_set: ConstraintSet, dry_run: bool):
        existing = list(
            constraint_set.constraints.filter(level='regulatory').order_by('order')
        )

        # ── Suppressions ──────────────────────────────────────────────────────
        to_remove = [c for c in existing if _should_remove(c.description)]
        for c in to_remove:
            self.stdout.write(f'  🗑  Supprime : {c.description}')
            if not dry_run:
                c.delete()

        # Recharger après suppressions
        if not dry_run:
            existing = list(
                constraint_set.constraints.filter(level='regulatory').order_by('order')
            )
        else:
            existing = [c for c in existing if not _should_remove(c.description)]

        existing_descriptions = {c.description for c in existing}

        # ── Ajouts / mises à jour ──────────────────────────────────────────────
        for order, description in REGULATORY_TARGET:
            if description in existing_descriptions:
                # Mettre à jour l'ordre si nécessaire
                match = next((c for c in existing if c.description == description), None)
                if match and match.order != order:
                    self.stdout.write(f'  🔄 Réordonne (ordre {match.order}→{order}) : {description}')
                    if not dry_run:
                        match.order = order
                        match.save(update_fields=['order'])
            else:
                self.stdout.write(f'  ✅ Ajoute : {description}')
                if not dry_run:
                    constraint_set.constraints.create(
                        level='regulatory',
                        description=description,
                        order=order,
                        is_active=True,
                    )
