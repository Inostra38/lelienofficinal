"""Tests de l'API de demande/annulation de suppression de compte."""
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient

from apps.billing.models import Subscription
from apps.billing.tests.utils import make_pharmacy, set_subscription


def _client(pharmacy):
    c = APIClient()
    c.force_authenticate(user=pharmacy)
    return c


class AccountDeleteRequestTests(TestCase):
    URL = '/api/account/delete/'

    def test_requires_password(self):
        p = make_pharmacy()
        resp = _client(p).delete(self.URL, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_wrong_password(self):
        p = make_pharmacy()
        resp = _client(p).delete(self.URL, {'password': 'WRONG'}, format='json')
        self.assertEqual(resp.status_code, 401)

    @patch('apps.core.views._get_collaborator')
    def test_collaborator_session_forbidden(self, mock_collab):
        mock_collab.return_value = MagicMock()  # session collaborateur
        p = make_pharmacy()
        resp = _client(p).delete(self.URL, {'password': 'pass1234'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_schedules_30_days_without_subscription(self):
        p = make_pharmacy()
        resp = _client(p).delete(self.URL, {'password': 'pass1234'}, format='json')
        self.assertEqual(resp.status_code, 200)
        p.refresh_from_db()
        self.assertIsNotNone(p.deletion_scheduled_for)
        delta = p.deletion_scheduled_for - timezone.now()
        self.assertGreater(delta, timedelta(days=29))
        self.assertLess(delta, timedelta(days=31))

    @patch('apps.billing.stripe_service.StripeService.cancel_subscription')
    def test_cancels_subscription_at_period_end(self, mock_cancel):
        p = make_pharmacy()
        period_end = timezone.now() + timedelta(days=12)
        sub = set_subscription(p, stripe_customer_id='cus_1', stripe_subscription_id='sub_1',
            status='active', current_period_end=period_end,
        )
        resp = _client(p).delete(self.URL, {'password': 'pass1234'}, format='json')
        self.assertEqual(resp.status_code, 200)
        mock_cancel.assert_called_once_with('sub_1')
        sub.refresh_from_db()
        self.assertTrue(sub.cancel_at_period_end)
        p.refresh_from_db()
        self.assertEqual(p.deletion_scheduled_for, period_end)

    def test_already_scheduled_conflict(self):
        p = make_pharmacy(deletion_scheduled_for=timezone.now() + timedelta(days=10))
        resp = _client(p).delete(self.URL, {'password': 'pass1234'}, format='json')
        self.assertEqual(resp.status_code, 409)


class AccountDeletionCancelTests(TestCase):
    URL = '/api/account/delete/cancel/'

    def test_no_scheduled_deletion_returns_400(self):
        p = make_pharmacy()
        resp = _client(p).post(self.URL, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch('stripe.Subscription.modify')
    def test_cancels_scheduled_deletion_and_resumes_stripe(self, mock_modify):
        p = make_pharmacy(deletion_scheduled_for=timezone.now() + timedelta(days=10))
        p.deletion_requested_at = timezone.now()
        p.save()
        set_subscription(p, stripe_customer_id='cus_1', stripe_subscription_id='sub_1',
            status='active', cancel_at_period_end=True,
        )
        resp = _client(p).post(self.URL, {}, format='json')
        self.assertEqual(resp.status_code, 200)
        mock_modify.assert_called_once_with('sub_1', cancel_at_period_end=False)
        p.refresh_from_db()
        self.assertIsNone(p.deletion_scheduled_for)
        self.assertIsNone(p.deletion_requested_at)

    @patch('apps.core.views._get_collaborator')
    def test_collaborator_session_forbidden(self, mock_collab):
        mock_collab.return_value = MagicMock()
        p = make_pharmacy(deletion_scheduled_for=timezone.now() + timedelta(days=10))
        resp = _client(p).post(self.URL, {}, format='json')
        self.assertEqual(resp.status_code, 403)
