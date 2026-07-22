"""Verrou de l'offre gratuite.

Le tableau de bord est gratuit **définitivement et sans condition**. Ces tests
échouent si quelqu'un place ``HasPaidAccess`` sur une vue du périmètre gratuit,
ou retire la règle des modules payants.

Ils portent une décision commerciale, pas seulement technique : ne pas les
« réparer » en les assouplissant sans arbitrage produit.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.billing.models import Subscription
from apps.billing.tests.utils import make_pharmacy, set_subscription


class FreeTierAlwaysOpenTests(TestCase):
    """Le tableau de bord répond, quel que soit l'état de l'abonnement."""

    #: Endpoints du périmètre gratuit. En ajouter ici quand le dashboard grandit.
    FREE_ENDPOINTS = [
        '/api/categories/',
        '/api/catalog/cards/',
        '/api/pharmacy/me/',
    ]

    def setUp(self):
        self.pharmacy = make_pharmacy()
        self.client = APIClient()
        self.client.force_authenticate(user=self.pharmacy)

    def _assert_all_free_endpoints_ok(self, situation):
        for url in self.FREE_ENDPOINTS:
            with self.subTest(url=url, situation=situation):
                response = self.client.get(url)
                self.assertNotEqual(
                    response.status_code, 402,
                    f"{url} renvoie 402 alors que le tableau de bord est gratuit ({situation}).",
                )
                self.assertLess(
                    response.status_code, 400,
                    f"{url} échoue ({response.status_code}) — situation : {situation}.",
                )

    def test_gratuit_sans_aucun_abonnement(self):
        self._assert_all_free_endpoints_ok('aucun objet Subscription')

    def test_gratuit_apres_essai_expire(self):
        set_subscription(self.pharmacy, status=Subscription.Status.TRIALING,
            trial_ends_at=timezone.now() - timedelta(days=1),
        )
        self._assert_all_free_endpoints_ok('essai expiré')

    def test_gratuit_quand_suspendu_pour_impaye(self):
        set_subscription(self.pharmacy, status=Subscription.Status.SUSPENDED,
            suspended_at=timezone.now(),
        )
        self._assert_all_free_endpoints_ok('abonnement suspendu')

    def test_gratuit_quand_resilie(self):
        set_subscription(self.pharmacy, status=Subscription.Status.CANCELED,
        )
        self._assert_all_free_endpoints_ok('abonnement résilié')


class PaidModulesGatedTests(TestCase):
    """Les modules payants coupent — et renvoient 402, jamais 403."""

    PAID_ENDPOINTS = [
        '/api/tasks/',
        '/api/messaging/conversations/',
    ]

    def setUp(self):
        self.pharmacy = make_pharmacy()
        self.client = APIClient()
        self.client.force_authenticate(user=self.pharmacy)

    def test_402_quand_essai_expire(self):
        set_subscription(self.pharmacy, status=Subscription.Status.TRIALING,
            trial_ends_at=timezone.now() - timedelta(days=1),
        )
        for url in self.PAID_ENDPOINTS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 402)

    def test_ouvert_pendant_essai(self):
        set_subscription(self.pharmacy, status=Subscription.Status.TRIALING,
            trial_ends_at=timezone.now() + timedelta(days=10),
        )
        for url in self.PAID_ENDPOINTS:
            with self.subTest(url=url):
                self.assertNotEqual(self.client.get(url).status_code, 402)


class AccessRuleTests(TestCase):
    """Règle d'accès calculée sur les dates, sans dépendance à Celery."""

    def setUp(self):
        self.pharmacy = make_pharmacy()

    def _sub(self, **kwargs):
        return Subscription(pharmacy=self.pharmacy, **kwargs)

    def test_essai_en_cours_autorise(self):
        sub = self._sub(
            status=Subscription.Status.TRIALING,
            trial_ends_at=timezone.now() + timedelta(days=1),
        )
        self.assertTrue(sub.is_access_allowed)

    def test_essai_expire_refuse_sans_intervention_de_celery(self):
        """Le statut reste TRIALING : c'est la date qui tranche."""
        sub = self._sub(
            status=Subscription.Status.TRIALING,
            trial_ends_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertFalse(sub.is_access_allowed)
        self.assertEqual(sub.access_denied_reason, 'trial_expired')

    def test_impaye_dans_le_delai_de_grace_autorise(self):
        sub = self._sub(
            status=Subscription.Status.PAST_DUE,
            past_due_since=timezone.now() - timedelta(days=6),
        )
        self.assertTrue(sub.is_access_allowed)

    def test_impaye_au_dela_de_sept_jours_refuse(self):
        sub = self._sub(
            status=Subscription.Status.PAST_DUE,
            past_due_since=timezone.now() - timedelta(days=7, seconds=1),
        )
        self.assertFalse(sub.is_access_allowed)
        self.assertEqual(sub.access_denied_reason, 'payment_failed')

    def test_suspendu_refuse(self):
        self.assertFalse(self._sub(status=Subscription.Status.SUSPENDED).is_access_allowed)

    def test_actif_autorise(self):
        self.assertTrue(self._sub(status=Subscription.Status.ACTIVE).is_access_allowed)

    def test_grace_days_left_compte_a_rebours_pendant_impaye(self):
        # Impayé de 3 jours → il reste ~4 jours sur les 7 de grâce (arrondi sup.).
        sub = self._sub(
            status=Subscription.Status.PAST_DUE,
            past_due_since=timezone.now() - timedelta(days=3),
        )
        self.assertEqual(sub.grace_days_left, 4)

    def test_grace_days_left_zero_quand_grace_depassee(self):
        sub = self._sub(
            status=Subscription.Status.PAST_DUE,
            past_due_since=timezone.now() - timedelta(days=7, seconds=1),
        )
        self.assertEqual(sub.grace_days_left, 0)

    def test_grace_days_left_none_hors_impaye(self):
        # Aucun compte à rebours n'a de sens hors d'un impayé en cours.
        self.assertIsNone(self._sub(status=Subscription.Status.ACTIVE).grace_days_left)
        self.assertIsNone(self._sub(
            status=Subscription.Status.TRIALING,
            trial_ends_at=timezone.now() + timedelta(days=10),
        ).grace_days_left)
