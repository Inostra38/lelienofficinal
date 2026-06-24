"""
Tests paye_analytics — caching du résultat.

Pour un mois passé :
  - Premier appel → cache miss → calcul → cache.set()
  - Deuxième appel → cache hit → retour immédiat sans recalculer
  - cache.get() doit être appelé
Pour le mois en cours :
  - Aucun appel à cache.get() / cache.set()
"""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from apps.core.models import Pharmacy
from apps.planning.paye_analytics import compute_paye_summary


def _ym_offset(months_delta):
    """(année, mois) décalés de `months_delta` mois par rapport à aujourd'hui.

    Les tests doivent rester valides quelle que soit la date d'exécution :
    `compute_paye_summary` distingue passé / en cours / futur via `date.today()`,
    on dérive donc les mois de référence de la même source plutôt que de les figer.
    """
    today = date.today()
    idx = today.year * 12 + (today.month - 1) + months_delta
    return idx // 12, idx % 12 + 1


def _make_pharmacy(email):
    p = Pharmacy.objects.create(
        email=email,
        nom_officine="Pharmacie Cache",
        onboarding_completed=True,
        is_active=True,
    )
    p.set_password("test")
    p.save()
    return p


class TestPayeAnalyticsCache(TestCase):
    """
    On mocke `apps.planning.paye_analytics.cache` pour vérifier les appels
    sans dépendre du backend de cache configuré (DummyCache en tests).
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy("cache_test@test.com")

    def test_mois_passe_set_en_cache(self):
        """Premier appel sur mois passé → cache.set() appelé avec la clé correcte."""
        year, month = _ym_offset(-1)  # mois précédent = passé
        with patch('apps.planning.paye_analytics.cache') as mock_cache:
            mock_cache.get.return_value = None  # cache miss
            compute_paye_summary(self.pharmacy, year, month)
            mock_cache.set.assert_called_once()
            # Vérifier la clé de cache
            cache_key = f'paye:{self.pharmacy.pk}:{year}-{month:02d}'
            mock_cache.get.assert_called_once_with(cache_key)

    def test_mois_passe_retourne_depuis_cache(self):
        """Appel sur mois passé avec cache hit → retour immédiat, set() non appelé."""
        year, month = _ym_offset(-1)  # mois précédent = passé
        cached_data = {'month': f'{year}-{month:02d}', 'collaborateurs': [], 'from_cache': True}
        with patch('apps.planning.paye_analytics.cache') as mock_cache:
            mock_cache.get.return_value = cached_data
            result = compute_paye_summary(self.pharmacy, year, month)
            self.assertEqual(result, cached_data)
            mock_cache.set.assert_not_called()

    def test_mois_en_cours_pas_de_cache(self):
        """Pour le mois en cours, cache.get/set ne sont pas appelés."""
        year, month = _ym_offset(0)  # mois courant
        with patch('apps.planning.paye_analytics.cache') as mock_cache:
            mock_cache.get.return_value = None
            compute_paye_summary(self.pharmacy, year, month)
            mock_cache.get.assert_not_called()
            mock_cache.set.assert_not_called()

    def test_mois_futur_pas_de_cache(self):
        """Pour un mois futur, cache.get/set ne sont pas appelés."""
        year, month = _ym_offset(1)  # mois suivant = futur
        with patch('apps.planning.paye_analytics.cache') as mock_cache:
            mock_cache.get.return_value = None
            compute_paye_summary(self.pharmacy, year, month)
            mock_cache.get.assert_not_called()
            mock_cache.set.assert_not_called()
