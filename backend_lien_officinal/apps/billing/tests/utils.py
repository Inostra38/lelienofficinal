"""Helpers partagés pour les tests billing."""
from apps.core.models import Pharmacy

_counter = 0


def make_pharmacy(**extra):
    """Crée une pharmacie de test avec un email unique. `extra` patche les champs."""
    global _counter
    _counter += 1
    pharmacy = Pharmacy.objects.create_user(
        email=f'billing_test_{_counter}@example.com',
        password='pass1234',
        nom_officine='Pharmacie Test',
    )
    if extra:
        for key, value in extra.items():
            setattr(pharmacy, key, value)
        pharmacy.save()
    return pharmacy


def set_subscription(pharmacy, **fields):
    """Positionne l'abonnement d'une pharmacie de test.

    Depuis le 2026-07-19, apps.billing.signals crée un abonnement d'essai à la
    naissance de toute pharmacie. `Subscription.objects.create()` viole donc la
    contrainte OneToOne : les tests doivent mettre à jour l'existant.
    """
    from apps.billing.models import Subscription

    subscription, _ = Subscription.objects.get_or_create(pharmacy=pharmacy)
    for key, value in fields.items():
        setattr(subscription, key, value)
    subscription.save()
    return subscription
