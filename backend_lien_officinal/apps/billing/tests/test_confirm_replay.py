"""Q04 — ConfirmSubscriptionView : garde anti-rejeu.

Un double POST /api/billing/confirm/ créait un second abonnement Stripe et
écrasait l'id du premier → abonnement orphelin facturé + double prélèvement.
"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Pharmacy
from apps.billing.models import Subscription

_n = 0


def _pharma():
    global _n
    _n += 1
    return Pharmacy.objects.create_user(email=f"bil_{_n}@t.com", password="x", nom_officine="Ph")


def _client(p):
    c = APIClient()
    c.force_authenticate(user=p)
    return c


class TestConfirmReplayGuard(TestCase):
    @patch('apps.billing.views.StripeService.create_subscription')
    @patch('apps.billing.views.stripe.Customer.modify')
    @patch('apps.billing.views.stripe.PaymentMethod.attach')
    def test_abonnement_deja_actif_renvoie_409(self, mock_attach, mock_modify, mock_create):
        pharma = _pharma()
        Subscription.objects.create(
            pharmacy=pharma, stripe_customer_id='cus_1',
            stripe_subscription_id='sub_existant',  # déjà actif
        )
        resp = _client(pharma).post('/api/billing/confirm/', {'payment_method_id': 'pm_1'}, format='json')

        self.assertEqual(resp.status_code, 409)
        mock_create.assert_not_called()   # aucun second abonnement Stripe créé
        mock_attach.assert_not_called()   # on sort avant tout appel Stripe

    @patch('apps.billing.views.StripeService.create_subscription')
    @patch('apps.billing.views.stripe.Customer.modify')
    @patch('apps.billing.views.stripe.PaymentMethod.attach')
    def test_premier_abonnement_appelle_stripe(self, mock_attach, mock_modify, mock_create):
        pharma = _pharma()
        Subscription.objects.create(pharmacy=pharma, stripe_customer_id='cus_1')  # pas encore d'abo
        mock_create.return_value = type('S', (), {'id': 'sub_new', 'trial_end': 1893456000})()

        resp = _client(pharma).post('/api/billing/confirm/', {'payment_method_id': 'pm_1'}, format='json')

        self.assertEqual(resp.status_code, 200)
        mock_create.assert_called_once()
        pharma.subscription.refresh_from_db()
        self.assertEqual(pharma.subscription.stripe_subscription_id, 'sub_new')
