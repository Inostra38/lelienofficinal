"""Crée des collaborateurs de test pour une pharmacie.

Sert à la recette de l'UI de sélection collaborateur (recherche + liste au-delà
de 12). Arguments simples (pas de guillemets) → utilisable en one-off Scalingo.

    manage.py create_test_collaborators --email webmaster@lienofficinal.fr --count 12
"""

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Pharmacy
from apps.team.models import Collaborator

# Quelques initiales se télescopent volontairement (Marie Bernard / Marc Blanc →
# « MB ») pour vérifier que la recherche par nom lève l'ambiguïté.
_NAMES = [
    ('Marie', 'Bernard'), ('Marc', 'Blanc'), ('Sophie', 'Dubois'),
    ('Lucas', 'Moreau'), ('Emma', 'Laurent'), ('Louis', 'Lefebvre'),
    ('Léa', 'Laurent'), ('Nathan', 'Simon'), ('Chloé', 'Garcia'),
    ('Hugo', 'Roux'), ('Manon', 'Fournier'), ('Théo', 'Girard'),
    ('Camille', 'Bonnet'), ('Jules', 'Dupont'), ('Alice', 'Mercier'),
    ('Paul', 'Faure'),
]

_COLORS = [
    '#1f8a5a', '#2f7d8c', '#7a7a2f', '#6b5aa8', '#a85a6b', '#c0562f',
    '#3d7a3d', '#8a4f7a', '#5a6b8a', '#a87f2f', '#4f8a8a', '#7a5a2f',
    '#5a8a4f', '#8a5a5a', '#5a7a8a', '#7a8a5a',
]


class Command(BaseCommand):
    help = "Crée des collaborateurs de test pour une pharmacie (recette UI)."

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help="Email de la pharmacie cible.")
        parser.add_argument('--count', type=int, default=12, help="Nombre à créer.")
        parser.add_argument('--pin', default='1234', help="PIN commun (test).")

    def handle(self, *args, **options):
        pharmacy = Pharmacy.objects.filter(email=options['email']).first()
        if pharmacy is None:
            known = ', '.join(Pharmacy.objects.values_list('email', flat=True)[:10])
            raise CommandError(f"Pharmacie « {options['email']} » introuvable. Connues : {known}")

        created = 0
        for i in range(options['count']):
            first, last = _NAMES[i % len(_NAMES)]
            # Au-delà de la liste, suffixer pour respecter l'unicité (pharmacy, prénom, nom).
            if i >= len(_NAMES):
                last = f'{last}{i}'
            if Collaborator.objects.filter(
                pharmacy=pharmacy, first_name=first, last_name=last
            ).exists():
                continue
            collab = Collaborator(
                pharmacy=pharmacy,
                first_name=first,
                last_name=last,
                color=_COLORS[i % len(_COLORS)],
                display_order=i,
            )
            collab.set_pin(options['pin'])
            collab.save()
            created += 1

        total = Collaborator.objects.filter(pharmacy=pharmacy, is_active=True).count()
        self.stdout.write(
            f"{created} collaborateurs de test créés (PIN {options['pin']}). "
            f"Total actif pour {options['email']} : {total}."
        )
