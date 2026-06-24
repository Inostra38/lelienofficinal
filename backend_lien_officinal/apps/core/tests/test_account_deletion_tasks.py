"""Tests de l'exécution différée : balayage quotidien + déclenchement webhook."""
import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.utils import timezone

from apps.core.tasks import execute_scheduled_deletions
from apps.billing.models import Subscription
from apps.billing.tests.utils import make_pharmacy

WEBHOOK_URL = '/api/billing/webhook/stripe/'


class ScheduledDeletionsSweepTests(TestCase):

    def test_anonymizes_due_account(self):
        p = make_pharmacy(deletion_scheduled_for=timezone.now() - timedelta(minutes=1))
        self.assertEqual(execute_scheduled_deletions(), 1)
        p.refresh_from_db()
        self.assertIsNotNone(p.anonymized_at)
        self.assertFalse(p.is_active)

    def test_skips_future_schedule(self):
        p = make_pharmacy(deletion_scheduled_for=timezone.now() + timedelta(days=5))
        self.assertEqual(execute_scheduled_deletions(), 0)
        p.refresh_from_db()
        self.assertIsNone(p.anonymized_at)

    def test_skips_unscheduled(self):
        make_pharmacy()
        self.assertEqual(execute_scheduled_deletions(), 0)

    def test_skips_already_anonymized(self):
        make_pharmacy(
            deletion_scheduled_for=timezone.now() - timedelta(days=1),
            anonymized_at=timezone.now(),
        )
        self.assertEqual(execute_scheduled_deletions(), 0)


class SubscriptionDeletedWebhookTriggerTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('apps.core.tasks.execute_account_deletion_task')
    @patch('apps.billing.views.StripeService.construct_webhook_event', return_value=None)
    def test_pending_deletion_triggers_execution(self, _mock, mock_task):
        p = make_pharmacy(deletion_scheduled_for=timezone.now())
        Subscription.objects.create(pharmacy=p, stripe_subscription_id='sub_del', status='active')
        resp = self.client.post(
            WEBHOOK_URL,
            data=json.dumps({'type': 'customer.subscription.deleted',
                             'data': {'object': {'id': 'sub_del'}}}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_called_once_with(p.id)

    @patch('apps.core.tasks.execute_account_deletion_task')
    @patch('apps.billing.views.StripeService.construct_webhook_event', return_value=None)
    def test_no_pending_deletion_does_not_trigger(self, _mock, mock_task):
        p = make_pharmacy()  # pas de suppression programmée
        Subscription.objects.create(pharmacy=p, stripe_subscription_id='sub_x', status='active')
        resp = self.client.post(
            WEBHOOK_URL,
            data=json.dumps({'type': 'customer.subscription.deleted',
                             'data': {'object': {'id': 'sub_x'}}}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_not_called()
