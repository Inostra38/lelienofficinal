"""Abonnement rétroactif pour les pharmacies antérieures à l'offre freemium.

Avant le 2026-07-19, aucun ``Subscription`` n'était créé à l'inscription : il
n'apparaissait qu'à la première visite de Compte > Facturation. Les comptes
existants n'en ont donc aucun.

Or ``HasPaidAccess`` refuse une pharmacie sans abonnement. Sans ce backfill,
le déploiement couperait planning, qualité, tâches, messagerie et SMS pour
tous les comptes existants — le tableau de bord, lui, resterait accessible.

Statut ``active`` : ces comptes précèdent la mise en place du modèle
commercial, on ne leur applique pas l'essai rétroactivement.

Exécuté dans la même transaction que le reste du déploiement : il n'existe
aucun instant où les comptes sont privés de leurs modules.
"""

from django.db import migrations


def create_missing_subscriptions(apps, schema_editor):
    Pharmacy = apps.get_model('core', 'Pharmacy')
    Subscription = apps.get_model('billing', 'Subscription')

    existing = set(Subscription.objects.values_list('pharmacy_id', flat=True))
    missing = Pharmacy.objects.exclude(id__in=existing)

    Subscription.objects.bulk_create([
        # 'active' en dur : les TextChoices du modèle ne sont pas accessibles
        # depuis l'état historique fourni par apps.get_model.
        Subscription(pharmacy_id=pharmacy.id, status='active', plan='small')
        for pharmacy in missing
    ])


def noop_reverse(apps, schema_editor):
    """Pas de suppression au retour arrière.

    On ne saurait pas distinguer les abonnements créés ici de ceux créés
    ensuite par les utilisateurs — les supprimer détruirait des données
    légitimes, y compris des liens vers Stripe.
    """


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0006_subscription_past_due_since'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_missing_subscriptions, noop_reverse),
    ]
