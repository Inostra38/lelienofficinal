"""Tests des endpoints API billing (DRF, JWT)."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.billing.models import Invoice, PromoCode
from apps.billing.tests.utils import make_pharmacy


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
