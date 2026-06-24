"""Tests des tâches Celery billing : crédit SMS (idempotent) et génération de facture."""
from unittest.mock import patch

from django.test import TestCase

from apps.billing import tasks
from apps.billing.models import Invoice, SmsCreditTransaction, Subscription
from apps.billing.tests.utils import make_pharmacy


class CreditSmsBalanceTests(TestCase):
    def setUp(self):
        self.pharmacy = make_pharmacy(sms_credits=10)

    @patch('apps.billing.tasks.generate_sms_receipt')
    def test_credits_balance_and_logs_transaction(self, mock_receipt):
        tasks.credit_sms_balance.apply(args=[self.pharmacy.id, 100, 'pi_1', 900])
        self.pharmacy.refresh_from_db()
        self.assertEqual(self.pharmacy.sms_credits, 110)
        self.assertEqual(
            SmsCreditTransaction.objects.filter(pharmacy=self.pharmacy).count(), 1
        )
        mock_receipt.delay.assert_called_once()

    @patch('apps.billing.tasks.generate_sms_receipt')
    def test_idempotent_on_same_payment_intent(self, _mock_receipt):
        tasks.credit_sms_balance.apply(args=[self.pharmacy.id, 100, 'pi_1', 900])
        tasks.credit_sms_balance.apply(args=[self.pharmacy.id, 100, 'pi_1', 900])
        self.pharmacy.refresh_from_db()
        self.assertEqual(self.pharmacy.sms_credits, 110)  # pas 210
        self.assertEqual(
            SmsCreditTransaction.objects.filter(pharmacy=self.pharmacy).count(), 1
        )


class GenerateSubscriptionInvoiceTests(TestCase):
    @patch('apps.billing.email_service.send_subscription_invoice_email')
    @patch('apps.billing.pdf_service.generate_signed_url', return_value='https://signed')
    @patch('apps.billing.pdf_service.read_pdf_bytes', return_value=b'%PDF-x')
    @patch('apps.billing.pdf_service.generate_subscription_invoice_pdf')
    def test_creates_invoice_and_sends_email(self, mock_pdf, _mread, _msign, mock_email):
        pharmacy = make_pharmacy()
        Subscription.objects.create(
            pharmacy=pharmacy, stripe_subscription_id='sub_1',
            plan='small', status='active',
        )
        tasks.generate_subscription_invoice.apply(args=[pharmacy.id, 'in_1', 3900])

        self.assertEqual(Invoice.objects.filter(stripe_invoice_id='in_1').count(), 1)
        mock_pdf.assert_called_once()
        mock_email.assert_called_once()

    @patch('apps.billing.email_service.send_subscription_invoice_email')
    @patch('apps.billing.pdf_service.generate_signed_url', return_value='https://signed')
    @patch('apps.billing.pdf_service.read_pdf_bytes', return_value=b'%PDF-x')
    @patch('apps.billing.pdf_service.generate_subscription_invoice_pdf')
    def test_idempotent_on_same_stripe_invoice(self, mock_pdf, _mread, _msign, _memail):
        pharmacy = make_pharmacy()
        Subscription.objects.create(
            pharmacy=pharmacy, stripe_subscription_id='sub_1',
            plan='small', status='active',
        )
        tasks.generate_subscription_invoice.apply(args=[pharmacy.id, 'in_1', 3900])
        tasks.generate_subscription_invoice.apply(args=[pharmacy.id, 'in_1', 3900])
        self.assertEqual(Invoice.objects.filter(stripe_invoice_id='in_1').count(), 1)
        self.assertEqual(mock_pdf.call_count, 1)  # 2e passage court-circuité
