"""Tests du webhook Stripe : vérification de signature et routage des événements."""
import json
from unittest.mock import patch

import stripe
from django.test import Client, TestCase

from apps.billing.models import Subscription
from apps.billing.tests.utils import make_pharmacy

WEBHOOK_URL = '/api/billing/webhook/stripe/'


def _post(client, event):
    return client.post(WEBHOOK_URL, data=json.dumps(event), content_type='application/json')


class StripeWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('apps.billing.views.StripeService.construct_webhook_event',
           side_effect=stripe.SignatureVerificationError('bad', 'sig'))
    def test_invalid_signature_returns_400(self, _mock):
        resp = self.client.post(WEBHOOK_URL, data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    # Cas valides : la signature est OK (mock ne lève pas). Le handler travaille
    # sur le JSON brut du payload (stripe v15 → pas de .get() sur les objets ressources).
    @patch('apps.billing.views.StripeService.construct_webhook_event', return_value=None)
    def test_unknown_event_returns_200(self, _mock):
        resp = _post(self.client, {'type': 'some.unhandled.event', 'data': {'object': {}}})
        self.assertEqual(resp.status_code, 200)

    @patch('apps.billing.views.StripeService.construct_webhook_event', return_value=None)
    def test_subscription_deleted_sets_canceled(self, _mock):
        pharmacy = make_pharmacy()
        sub = Subscription.objects.create(
            pharmacy=pharmacy, stripe_subscription_id='sub_1', status='active',
        )
        resp = _post(self.client, {
            'type': 'customer.subscription.deleted',
            'data': {'object': {'id': 'sub_1'}},
        })
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.CANCELED)

    @patch('apps.billing.views.credit_sms_balance')
    @patch('apps.billing.views.StripeService.construct_webhook_event', return_value=None)
    def test_payment_intent_sms_pack_triggers_credit(self, _mock, mock_task):
        resp = _post(self.client, {
            'type': 'payment_intent.succeeded',
            'data': {'object': {
                'id': 'pi_1', 'amount': 900,
                'metadata': {'type': 'sms_pack', 'pharmacy_id': '5'},
            }},
        })
        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_called_once()
        # 900 cents → 100 SMS
        self.assertEqual(mock_task.delay.call_args.kwargs['quantity'], 100)

    @patch('apps.billing.views.credit_sms_balance')
    @patch('apps.billing.views.StripeService.construct_webhook_event', return_value=None)
    def test_payment_intent_non_sms_ignored(self, _mock, mock_task):
        resp = _post(self.client, {
            'type': 'payment_intent.succeeded',
            'data': {'object': {'id': 'pi_2', 'amount': 900, 'metadata': {'type': 'autre'}}},
        })
        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_not_called()

    @patch('apps.billing.views.generate_subscription_invoice')
    @patch('apps.billing.views.StripeService.construct_webhook_event', return_value=None)
    def test_invoice_paid_new_api_format(self, _mock, mock_gen):
        # API 2025+/dahlia : l'id d'abonnement est dans parent.subscription_details.
        pharmacy = make_pharmacy()
        sub = Subscription.objects.create(
            pharmacy=pharmacy, stripe_subscription_id='sub_x', status='trialing',
        )
        resp = _post(self.client, {
            'type': 'invoice.paid',
            'data': {'object': {
                'id': 'in_1', 'amount_paid': 3900, 'subscription': None,
                'parent': {'subscription_details': {'subscription': 'sub_x'}},
                'lines': {'data': [{'period': {'end': 1893456000}}]},
            }},
        })
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        mock_gen.delay.assert_called_once()
