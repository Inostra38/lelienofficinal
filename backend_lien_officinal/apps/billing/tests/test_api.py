"""Tests des endpoints API billing (DRF, JWT)."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.billing.models import Invoice, PromoCode, Subscription
from apps.billing.tests.utils import make_pharmacy, set_subscription


def _auth_client(pharmacy):
    client = APIClient()
    client.force_authenticate(user=pharmacy)
    return client


class BillingStatusViewTests(TestCase):
    def test_requires_auth(self):
        resp = APIClient().get('/api/billing/status/')
        self.assertEqual(resp.status_code, 401)

    def test_status_without_subscription(self):
        pharmacy = make_pharmacy(sms_credits=42)
        # Le signal en crée un à l'inscription : on le retire pour atteindre
        # la branche « aucun abonnement » de la vue.
        Subscription.objects.filter(pharmacy=pharmacy).delete()
        resp = _auth_client(pharmacy).get('/api/billing/status/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['subscription'])
        self.assertEqual(resp.data['sms_credit']['balance'], 42)
        self.assertIsNone(resp.data['promo'])


class SmsPackIntentViewTests(TestCase):
    def setUp(self):
        self.pharmacy = make_pharmacy()
        self.client = _auth_client(self.pharmacy)

    def test_invalid_pack_returns_400(self):
        resp = self.client.post('/api/billing/sms-pack/intent/', {'pack': 'X'}, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch('apps.billing.views.StripeService.create_sms_payment_intent')
    def test_valid_pack_returns_client_secret(self, mock_pi):
        mock_pi.return_value = type('PI', (), {'client_secret': 'cs_test_123'})()
        resp = self.client.post('/api/billing/sms-pack/intent/', {'pack': 'S'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['client_secret'], 'cs_test_123')
        self.assertEqual(resp.data['quantity'], 100)
        self.assertEqual(resp.data['amount_cents'], 900)


class InvoiceListViewTests(TestCase):
    def test_lists_only_own_invoices(self):
        p1 = make_pharmacy()
        p2 = make_pharmacy()
        Invoice.objects.create(
            pharmacy=p1, invoice_type='subscription',
            invoice_number='LLO-2026-000001', amount_ht=Decimal('1'), amount_ttc=Decimal('1'),
        )
        Invoice.objects.create(
            pharmacy=p2, invoice_type='subscription',
            invoice_number='LLO-2026-000002', amount_ht=Decimal('1'), amount_ttc=Decimal('1'),
        )
        resp = _auth_client(p1).get('/api/billing/invoices/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['invoice_number'], 'LLO-2026-000001')


class ValidatePromoCodeViewTests(TestCase):
    def setUp(self):
        self.pharmacy = make_pharmacy()
        self.client = _auth_client(self.pharmacy)
        PromoCode.objects.create(code='GIPHAR3', months_free=3)

    def test_valid_code(self):
        resp = self.client.post('/api/billing/promo/validate/', {'code': 'giphar3'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['valid'])
        self.assertEqual(resp.data['months_free'], 3)
        self.assertEqual(resp.data['trial_days'], 120)

    def test_unknown_code_404(self):
        resp = self.client.post('/api/billing/promo/validate/', {'code': 'NOPE'}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(resp.data['valid'])

    def test_missing_code_400(self):
        resp = self.client.post('/api/billing/promo/validate/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_validate_has_throttle_configured(self):
        """Anti brute-force : la vue impose bien le throttle promo (le 429 réel
        n'est pas testable ici — cache DummyCache en settings_test)."""
        from apps.billing.views import ValidatePromoCodeView, PromoValidateThrottle
        self.assertIn(PromoValidateThrottle, ValidatePromoCodeView.throttle_classes)
        self.assertEqual(PromoValidateThrottle.scope, 'promo_validate')


class UpdatePaymentMethodViewTests(TestCase):
    """Changement de RIB en autonomie."""

    def setUp(self):
        self.pharmacy = make_pharmacy()
        self.client = _auth_client(self.pharmacy)

    def test_404_without_subscription(self):
        Subscription.objects.filter(pharmacy=self.pharmacy).delete()
        resp = self.client.post('/api/billing/payment-method/',
                                {'payment_method_id': 'pm_1'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_400_without_payment_method(self):
        set_subscription(self.pharmacy, stripe_customer_id='cus_1')
        resp = self.client.post('/api/billing/payment-method/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch('apps.billing.views.stripe.Subscription.modify')
    @patch('apps.billing.views.stripe.Customer.modify')
    @patch('apps.billing.views.stripe.PaymentMethod.attach')
    def test_updates_payment_method(self, mock_attach, mock_cust, mock_sub):
        set_subscription(self.pharmacy, stripe_customer_id='cus_1', stripe_subscription_id='sub_1',
        )
        resp = self.client.post('/api/billing/payment-method/',
                                {'payment_method_id': 'pm_new'}, format='json')
        self.assertEqual(resp.status_code, 200)
        mock_attach.assert_called_once_with('pm_new', customer='cus_1')
        mock_cust.assert_called_once()
        mock_sub.assert_called_once_with('sub_1', default_payment_method='pm_new')


class CancelSubscriptionViewTests(TestCase):
    """Résiliation en fin de période + reprise."""

    def setUp(self):
        self.pharmacy = make_pharmacy()
        self.client = _auth_client(self.pharmacy)

    def test_404_without_subscription(self):
        Subscription.objects.filter(pharmacy=self.pharmacy).delete()
        resp = self.client.post('/api/billing/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_400_without_stripe_subscription(self):
        set_subscription(self.pharmacy, stripe_customer_id='cus_1')
        resp = self.client.post('/api/billing/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch('apps.billing.views.StripeService.cancel_subscription')
    def test_schedules_cancellation(self, mock_cancel):
        sub = set_subscription(self.pharmacy, stripe_customer_id='cus_1', stripe_subscription_id='sub_1',
        )
        resp = self.client.post('/api/billing/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 200)
        mock_cancel.assert_called_once_with('sub_1')
        sub.refresh_from_db()
        self.assertTrue(sub.cancel_at_period_end)

    @patch('apps.billing.views.stripe.Subscription.modify')
    def test_resume_clears_cancellation(self, mock_modify):
        sub = set_subscription(self.pharmacy, stripe_customer_id='cus_1', stripe_subscription_id='sub_1',
            cancel_at_period_end=True,
        )
        resp = self.client.post('/api/billing/resume/', {}, format='json')
        self.assertEqual(resp.status_code, 200)
        mock_modify.assert_called_once_with('sub_1', cancel_at_period_end=False)
        sub.refresh_from_db()
        self.assertFalse(sub.cancel_at_period_end)
