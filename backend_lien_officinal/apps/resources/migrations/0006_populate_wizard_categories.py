from django.db import migrations

WIZARD_CATEGORIES = [
    (1,  "Grossistes-répartiteurs"),
    (2,  "Laboratoires directs"),
    (3,  "Dépositaires"),
    (4,  "Back-office"),
    (5,  "Comptabilité & fiscalité"),
    (6,  "Ressources humaines"),
    (7,  "Qualité & conformité"),
    (8,  "Gestion des stocks"),
    (9,  "Outils patients"),
    (10, "Aide à la dispensation"),
    (11, "Aide au comptoir"),
    (12, "Mutuelles & tiers payant"),
    (13, "Messagerie patient"),
    (14, "Formation professionnelle"),
    (15, "Veille réglementaire"),
    (16, "Actualités pharmaceutiques"),
    (17, "Outils numériques"),
    (18, "Logiciels & LGO"),
    (19, "Télémédecine & téléservices"),
    (20, "Préparations magistrales"),
    (21, "Matériel médical & location"),
    (22, "Dermo-cosmétique & parapharmacie"),
    (99, "Autre"),  # Catégorie système fallback IA — non retournée dans la liste de sélection
]


def populate(apps, schema_editor):
    WizardCategory = apps.get_model('resources', 'WizardCategory')
    for ordre, nom in WIZARD_CATEGORIES:
        WizardCategory.objects.create(nom=nom, ordre=ordre, is_active=True)


def depopulate(apps, schema_editor):
    WizardCategory = apps.get_model('resources', 'WizardCategory')
    WizardCategory.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0005_add_wizard_category'),
    ]

    operations = [
        migrations.RunPython(populate, depopulate),
    ]
