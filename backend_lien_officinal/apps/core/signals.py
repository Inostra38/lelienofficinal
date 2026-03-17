from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='core.Pharmacy')
def create_default_sms_templates(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import SMSTemplate
    templates = [
        {
            'title': 'Commande prête',
            'content': (
                'Bonjour {{patient.civilite}} {{patient.nom}}, votre commande est prête '
                'à être retirée. À bientôt ! {{pharmacie.nom}}'
            ),
        },
        {
            'title': 'Produit manquant',
            'content': (
                'Bonjour {{patient.civilite}} {{patient.nom}}, nous sommes désolés, '
                'le produit demandé est momentanément indisponible. {{pharmacie.nom}}'
            ),
        },
        {
            'title': 'Rappel ordonnance',
            'content': (
                'Bonjour {{patient.civilite}} {{patient.nom}}, pensez à renouveler '
                'votre ordonnance. Notre équipe est à votre disposition. {{pharmacie.nom}}'
            ),
        },
    ]
    for t in templates:
        SMSTemplate.objects.create(pharmacy=instance, **t)
