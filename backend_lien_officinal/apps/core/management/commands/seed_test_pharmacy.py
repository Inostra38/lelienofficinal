from django.core.management.base import BaseCommand
from apps.core.models import Pharmacy
from apps.resources.models import Category, ResourceCard, ResourceItem, WizardCategory


class Command(BaseCommand):
    help = 'Crée une pharmacie test avec catégories et ressources OFFICIAL'

    def handle(self, *args, **options):
        # Pharmacie
        p, created = Pharmacy.objects.get_or_create(
            email='test@lienofficinal.fr',
            defaults={
                'nom_officine': 'Pharmacie du Centre',
                'city': 'Paris',
                'onboarding_completed': True,
            }
        )
        if created:
            p.set_password('Test2026!')
            p.save()
            self.stdout.write(self.style.SUCCESS('Pharmacie creee: test@lienofficinal.fr / Test2026!'))
        else:
            self.stdout.write('Pharmacie existe deja')

        # Categories
        cat_noms = ['Grossistes', 'Laboratoires', 'Outils patients', 'Formation', 'Autre']
        for i, nom in enumerate(cat_noms):
            Category.objects.get_or_create(owner_pharmacy=p, nom=nom, defaults={'ordre': i})
        self.stdout.write(f'{len(cat_noms)} categories')

        # Ressources OFFICIAL
        officials = [
            ('Ameli', 'Portail officiel Assurance Maladie', 'https://www.ameli.fr'),
            ('Ordre des Pharmaciens', 'Institution professionnelle', 'https://www.ordre.pharmacien.fr'),
            ('Vidal', 'Base de donnees medicaments', 'https://www.vidal.fr'),
            ('ANSM', 'Agence nationale de securite du medicament', 'https://ansm.sante.fr'),
            ('Meddispar', 'Medicaments a dispensation particuliere', 'https://www.meddispar.fr'),
        ]
        for titre, desc, url in officials:
            card, _ = ResourceCard.objects.get_or_create(
                titre=titre, type='OFFICIAL',
                defaults={'description_officielle': desc}
            )
            ResourceItem.objects.get_or_create(
                card=card, type='WEB',
                defaults={'label': 'Site officiel', 'url': url}
            )
        self.stdout.write(f'{len(officials)} ressources OFFICIAL')

        # Wizard categories
        wizard_cats = [
            ('Grossistes-repartiteurs', 'Commandes, retours, avoirs'),
            ('Laboratoires', 'Informations produits, commandes directes'),
            ('Outils patients', 'Services patient, telemedecine, observance'),
            ('Formation', 'DPC, e-learning, webinaires'),
            ('Comptabilite', 'Logiciels comptables, facturation'),
            ('Assurance Maladie', 'Ameli, tiers payant, PEC'),
            ('Autre', 'Divers'),
        ]
        for i, (nom, desc) in enumerate(wizard_cats):
            WizardCategory.objects.get_or_create(nom=nom, defaults={'ordre': i, 'description': desc})
        self.stdout.write(f'{len(wizard_cats)} wizard categories')

        self.stdout.write(self.style.SUCCESS('DONE'))
