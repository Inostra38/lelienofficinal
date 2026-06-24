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
