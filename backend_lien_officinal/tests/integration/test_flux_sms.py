"""
Intégration : flux SMS complet
Crédits → Envoi → Débit crédits → Webhook DELIVERED
"""

from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy, SMSLog

_counter = 0


def _make_pharmacy(credits=10):
    global _counter
    _counter += 1
    pharmacy = Pharmacy.objects.create_user(
        email=f"pharma_fsms_{_counter}@test.com",
        password="pass",
        nom_officine="Pharmacie SMS",
    )
    pharmacy.sms_credits = credits
    pharmacy.save(update_fields=['sms_credits'])
    return pharmacy


def _pharmacy_client(pharmacy):
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


class TestFluxSMSComplet(TestCase):
    """
    Flux complet :
    1. Vérifier les crédits initiaux
    2. Envoyer un SMS (mock Celery + OVH)
    3. Vérifier le débit de crédits
    4. Simuler le webhook OVH → statut DELIVERED
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy(credits=10)
        self.client = _pharmacy_client(self.pharmacy)

    @patch('apps.core.tasks.send_sms_task')
    def test_flux_envoi_puis_webhook_delivered(self, mock_task):
        """Envoi SMS → débit crédits → webhook OVH → DELIVERED."""
        mock_task.delay.return_value = None

        # 1. Vérifier crédits initiaux
        resp_credits = self.client.get('/api/sms/credits/')
        self.assertEqual(resp_credits.status_code, 200)
        self.assertEqual(resp_credits.data['credits'], 10)

        # 2. Envoyer un SMS (1 crédit = 1 SMS court)
        resp_send = self.client.post(
            '/api/sms/send/',
            {
                'to': '+33612345678',
                'message': 'Bonjour, votre ordonnance est prête.',
                'recipient_name': 'Dupont Jean',
                'recipient_civilite': 'M',
                'motif': 'Ordonnance',
            },
            format='json',
        )
        self.assertEqual(resp_send.status_code, 202)
        self.assertIn('log_id', resp_send.data)
        log_id = resp_send.data['log_id']

        # 3. Vérifier le débit de crédits
        credits_used = resp_send.data.get('credits_remaining')
        self.assertIsNotNone(credits_used)
        self.assertLess(credits_used, 10)

        # Vérifier aussi en base
        self.pharmacy.refresh_from_db()
        self.assertEqual(self.pharmacy.sms_credits, credits_used)

        # 4. Log SMS créé avec statut PENDING
        log = SMSLog.objects.get(pk=log_id)
        self.assertEqual(log.status, SMSLog.Status.PENDING)
        self.assertGreater(log.credits_used, 0)

        # 5. Simuler un webhook OVH avec ovh_message_id
        log.ovh_message_id = 'test-msg-id-123'
        log.save(update_fields=['ovh_message_id'])

        resp_webhook = self.client.get(
            f'/api/sms/webhook/testtoken/?msgid=test-msg-id-123&status=OK',
        )
        self.assertEqual(resp_webhook.status_code, 200)

        log.refresh_from_db()
        self.assertEqual(log.status, SMSLog.Status.DELIVERED)

    @patch('apps.core.tasks.send_sms_task')
    def test_credits_insuffisants_402(self, mock_task):
        """Envoyer un SMS sans crédits suffisants → 402."""
        mock_task.delay.return_value = None

        pharmacy_broke = _make_pharmacy(credits=0)
        client = _pharmacy_client(pharmacy_broke)

        resp = client.post(
            '/api/sms/send/',
            {
                'to': '+33612345679',
                'message': 'Test message',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 402)

    @patch('apps.core.tasks.send_sms_task')
    def test_webhook_status_ko_failed(self, mock_task):
        """Webhook OVH avec status=KO → statut FAILED."""
        mock_task.delay.return_value = None

        resp_send = self.client.post(
            '/api/sms/send/',
            {
                'to': '+33687654321',
                'message': 'Message test échec.',
            },
            format='json',
        )
        self.assertEqual(resp_send.status_code, 202)
        log_id = resp_send.data['log_id']

        log = SMSLog.objects.get(pk=log_id)
        log.ovh_message_id = 'failed-msg-id-456'
        log.save(update_fields=['ovh_message_id'])

        resp_webhook = self.client.get(
            f'/api/sms/webhook/testtoken/?msgid=failed-msg-id-456&status=KO',
        )
        self.assertEqual(resp_webhook.status_code, 200)

        log.refresh_from_db()
        self.assertEqual(log.status, SMSLog.Status.FAILED)

    def test_webhook_msgid_inconnu_200(self):
        """Webhook avec msgid inconnu → 200 silencieux (pas d'erreur)."""
        resp = self.client.get(
            '/api/sms/webhook/testtoken/?msgid=unknown-id-999&status=OK',
        )
        self.assertEqual(resp.status_code, 200)

    def test_webhook_sans_msgid_400(self):
        """Webhook sans msgid → 400."""
        resp = self.client.get('/api/sms/webhook/testtoken/?status=OK')
        self.assertEqual(resp.status_code, 400)
