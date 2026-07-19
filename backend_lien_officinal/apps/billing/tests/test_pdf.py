"""Tests du pipeline PDF : calcul des montants, rendu WeasyPrint, mise à jour Invoice."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.billing import pdf_service
from apps.billing.models import Invoice, Subscription
from apps.billing.pdf_service import (
    _compute_amounts,
    _render_pdf,
    generate_subscription_invoice_pdf,
)
from apps.billing.tests.utils import make_pharmacy, set_subscription


class ComputeAmountsTests(TestCase):
    def test_39_euros_ttc(self):
        ht, tva, ttc = _compute_amounts(3900, Decimal('20.00'))
        self.assertEqual(ht, Decimal('32.50'))
        self.assertEqual(tva, Decimal('6.50'))
        self.assertEqual(ttc, Decimal('39.00'))

    def test_rounding_coherent(self):
        # 22,00 € TTC → HT 18,33 + TVA 3,67 = 22,00 (pas 22,01)
        ht, tva, ttc = _compute_amounts(2200, Decimal('20.00'))
        self.assertEqual(ttc, Decimal('22.00'))
        self.assertEqual(ht + tva, ttc)


class RenderPdfTests(TestCase):
    def test_render_returns_pdf_bytes(self):
        ctx = {
            'doc_type': 'Facture', 'invoice_number': 'LLO-2026-000001',
            'issued_at': '01/01/2026', 'paid_at': True,
            'emetteur_adresse': '1 rue Test', 'emetteur_siret': '000',
            'emetteur_tva_intra': 'FR00', 'emetteur_email': 't@t.fr',
            'capital_social': '1000', 'rcs': 'Paris', 'logo_base64': None,
            'pharmacy_name': 'Ph Test', 'pharmacy_adresse': '2 rue',
            'pharmacy_siret': '111', 'pharmacy_email': 'p@t.fr',
            'plan_label': 'Small', 'period_start': '01/01/2026', 'period_end': '31/01/2026',
            'amount_ht': '32.50', 'amount_tva': '6.50', 'amount_ttc': '39.00', 'tva_rate': '20.00',
        }
        pdf = _render_pdf('billing/invoice_subscription.html', ctx)
        self.assertTrue(pdf.startswith(b'%PDF'))


class GenerateSubscriptionInvoicePdfTests(TestCase):
    def test_updates_invoice_fields(self):
        pharmacy = make_pharmacy(
            address1='1 rue de la Paix', postal_code='75002',
            city='Paris', siret='12345678900011',
        )
        set_subscription(pharmacy, plan='small', status='active')
        invoice = Invoice.objects.create(
            pharmacy=pharmacy,
            invoice_type=Invoice.InvoiceType.SUBSCRIPTION,
            invoice_number='LLO-2026-000001',
            amount_ht=0, amount_ttc=0,
        )
        # On isole le stockage (pas d'écriture disque réelle)
        with patch.object(pdf_service, '_save_pdf', return_value='fakekey') as msave:
            key = generate_subscription_invoice_pdf(
                invoice=invoice, pharmacy=pharmacy,
                amount_ttc_cents=3900, period_start=None, period_end=None,
            )
        self.assertEqual(key, 'fakekey')
        msave.assert_called_once()
        invoice.refresh_from_db()
        self.assertEqual(invoice.pdf_storage_key, 'fakekey')
        self.assertEqual(invoice.amount_ht, Decimal('32.50'))
        self.assertEqual(invoice.amount_ttc, Decimal('39.00'))
        self.assertIsNotNone(invoice.paid_at)
