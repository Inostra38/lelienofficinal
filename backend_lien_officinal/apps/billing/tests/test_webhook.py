"""Tests du webhook Stripe : vérification de signature et routage des événements."""
from unittest.mock import patch

import stripe
from django.test import Client, TestCase

from apps.billing.models import Subscription
from apps.billing.tests.utils import make_pharmacy

WEBHOOK_URL = '/api/billing/webhook/stripe/'


class StripeWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('apps.billing.views.StripeService.construct_webhook_event',
           side_effect=stripe.SignatureVerificationError('bad', 'sig'))
    def test_invalid_signature_returns_400(self, _mock):
        resp = self.client.post(WEBHOOK_URL, data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    @patch('apps.billing.views.StripeService.construct_webhook_event')
    def test_unknown_event_returns_200(self, mock_evt):
        mock_evt.return_value = {'type': 'some.unhandled.event', 'data': {'object': {}}}
        resp = self.client.post(WEBHOOK_URL, data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 200)

    @patch('apps.billing.views.StripeService.construct_webhook_event')
    def test_subscription_deleted_sets_canceled(self, mock_evt):
        pharmacy = make_pharmacy()
        sub = Subscription.objects.create(
            pharmacy=pharmacy, stripe_subscription_id='sub_1', status='active',
        )
        mock_evt.return_value = {
            'type': 'customer.subscription.deleted',
            'data': {'object': {'id': 'sub_1'}},
        }
        resp = self.client.post(WEBHOOK_URL, data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.CANCELED)

    @patch('apps.billing.views.credit_sms_balance')
    @patch('apps.billing.views.StripeService.construct_webhook_event')
    def test_payment_intent_sms_pack_triggers_credit(self, mock_evt, mock_task):
        mock_evt.return_value = {
            'type': 'payment_intent.succeeded',
            'data': {'object': {
                'id': 'pi_1', 'amount': 900,
                'metadata': {'type': 'sms_pack', 'pharmacy_id': '5'},
            }},
        }
        resp = self.client.post(WEBHOOK_URL, data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_called_once()
        # 900 cents → 100 SMS
        self.assertEqual(mock_task.delay.call_args.kwargs['quantity'], 100)

    @patch('apps.billing.views.credit_sms_balance')
    @patch('apps.billing.views.StripeService.construct_webhook_event')
    def test_payment_intent_non_sms_ignored(self, mock_evt, mock_task):
        mock_evt.return_value = {
            'type': 'payment_intent.succeeded',
            'data': {'object': {'id': 'pi_2', 'amount': 900, 'metadata': {'type': 'autre'}}},
        }
        resp = self.client.post(WEBHOOK_URL, data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_not_called()
