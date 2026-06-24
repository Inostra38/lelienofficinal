"""Tests des modèles billing : numérotation des factures et validité des codes promo."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.billing.models import Invoice, PromoCode
from apps.billing.tests.utils import make_pharmacy


class InvoiceNumberTests(TestCase):
    def setUp(self):
        self.pharmacy = make_pharmacy()

    def _make_invoice(self, number):
        return Invoice.objects.create(
            pharmacy=self.pharmacy,
            invoice_type=Invoice.InvoiceType.SUBSCRIPTION,
            invoice_number=number,
            amount_ht=Decimal('10.00'),
            amount_ttc=Decimal('12.00'),
        )

    def test_first_number_is_000001(self):
        year = timezone.now().year
        self.assertEqual(
            Invoice.generate_invoice_number('subscription'),
            f'LLO-{year}-000001',
        )

    def test_numbers_are_sequential(self):
        year = timezone.now().year
        n1 = Invoice.generate_invoice_number('subscription')
        self._make_invoice(n1)
        n2 = Invoice.generate_invoice_number('sms_pack')
        self._make_invoice(n2)
        n3 = Invoice.generate_invoice_number('subscription')
        self.assertEqual(n1, f'LLO-{year}-000001')
        self.assertEqual(n2, f'LLO-{year}-000002')
        self.assertEqual(n3, f'LLO-{year}-000003')


class PromoCodeModelTests(TestCase):
    def test_trial_days_total(self):
        promo = PromoCode.objects.create(code='X3', months_free=3)
        self.assertEqual(promo.trial_days_total, 120)  # 30 + 3*30

    def test_is_valid_active(self):
        promo = PromoCode.objects.create(code='ACTIVE', months_free=1)
        self.assertTrue(promo.is_valid())

    def test_is_valid_inactive(self):
        promo = PromoCode.objects.create(code='OFF', months_free=1, is_active=False)
        self.assertFalse(promo.is_valid())

    def test_is_valid_expired(self):
        promo = PromoCode.objects.create(
            code='OLD', months_free=1,
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(promo.is_valid())

    def test_is_valid_quota_reached(self):
        promo = PromoCode.objects.create(
            code='FULL', months_free=1, max_uses=2, current_uses=2,
        )
        self.assertFalse(promo.is_valid())

    def test_is_valid_under_quota(self):
        promo = PromoCode.objects.create(
            code='ROOM', months_free=1, max_uses=2, current_uses=1,
        )
        self.assertTrue(promo.is_valid())
