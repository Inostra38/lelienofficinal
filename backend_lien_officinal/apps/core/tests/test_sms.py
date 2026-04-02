"""
Tests core/views_sms.py — SMSSendView, SMSPreviewView.
Les tests d'envoi et webhook de bout en bout sont couverts par
tests/integration/test_flux_sms.py. Ici on teste les cas unitaires.
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
    p = Pharmacy.objects.create_user(
        email=f"sms_{_counter}@test.com",
        password="pass",
        nom_officine="Pharmacie SMS",
    )
    p.sms_credits = credits
    p.save(update_fields=['sms_credits'])
    return p


def _pharmacy_client(pharmacy):
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


# ── SMSSendView ───────────────────────────────────────────────────────────────

class TestSMSSendDebitCredits(TestCase):
    """Envoi SMS — débit crédits correct, SMSLog créé."""

    def setUp(self):
        self.pharmacy = _make_pharmacy(credits=5)
        self.client = _pharmacy_client(self.pharmacy)

    @patch('apps.core.tasks.send_sms_task')
    def test_envoi_debite_credits_et_cree_smslog(self, mock_task):
        mock_task.delay.return_value = None
        resp = self.client.post(
            '/api/sms/send/',
            {'to': '+33612345678', 'message': 'Bonjour'},
            format='json',
        )
        self.assertEqual(resp.status_code, 202)
        # Crédits débités
        self.pharmacy.refresh_from_db()
        self.assertLess(self.pharmacy.sms_credits, 5)
        # SMSLog créé
        self.assertEqual(SMSLog.objects.filter(pharmacy=self.pharmacy).count(), 1)
        log = SMSLog.objects.get(pharmacy=self.pharmacy)
        self.assertEqual(log.status, SMSLog.Status.PENDING)
        # Celery appelé
        mock_task.delay.assert_called_once()


class TestSMSCreditsInsuffisants(TestCase):
    """Envoi SMS avec 0 crédits → 402, aucun SMSLog créé."""

    def setUp(self):
        self.pharmacy = _make_pharmacy(credits=0)
        self.client = _pharmacy_client(self.pharmacy)

    @patch('apps.core.tasks.send_sms_task')
    def test_402_si_credits_insuffisants(self, mock_task):
        resp = self.client.post(
            '/api/sms/send/',
            {'to': '+33612345678', 'message': 'Bonjour'},
            format='json',
        )
        self.assertEqual(resp.status_code, 402)
        self.assertEqual(SMSLog.objects.filter(pharmacy=self.pharmacy).count(), 0)
        mock_task.delay.assert_not_called()


class TestSMSMessageVide(TestCase):
    """Message vide → 400 avant consommation de crédits."""

    def setUp(self):
        self.pharmacy = _make_pharmacy(credits=10)
        self.client = _pharmacy_client(self.pharmacy)

    @patch('apps.core.tasks.send_sms_task')
    def test_400_message_vide(self, mock_task):
        resp = self.client.post(
            '/api/sms/send/',
            {'to': '+33612345678', 'message': ''},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        # Aucun crédit débité
        self.pharmacy.refresh_from_db()
        self.assertEqual(self.pharmacy.sms_credits, 10)
        mock_task.delay.assert_not_called()


# ── SMSPreviewView ────────────────────────────────────────────────────────────

class TestSMSPreviewEncodage(TestCase):
    """
    preview/ — détection correcte GSM-7 vs Unicode.
    Un message purement ASCII/GSM-7 → encoding 'GSM-7'.
    Un message avec caractère unicode (é, ê, ©…) → encoding 'Unicode'.
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.client = _pharmacy_client(self.pharmacy)

    def test_message_gsm7_encoding_correct(self):
        """Message ASCII pur → GSM-7 détecté, sms_count = 1."""
        resp = self.client.post(
            '/api/sms/preview/',
            {'content': 'Bonjour, votre ordonnance est prete.'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['encoding'], 'GSM-7')
        self.assertGreaterEqual(resp.data['sms_count'], 1)

    def test_message_unicode_encoding_correct(self):
        """Message avec caractères accentués français → Unicode détecté."""
        resp = self.client.post(
            '/api/sms/preview/',
            {'content': 'Bonjour, votre ordonnance est prête. À bientôt !'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['encoding'], 'Unicode')

    def test_sms_count_plus_eleve_en_unicode(self):
        """
        Pour un même message, le comptage Unicode nécessite plus de SMS
        que GSM-7 car la limite par message passe de 160 à 70 caractères.
        Un message de 100 caractères : 1 SMS GSM-7, 2 SMS Unicode.
        """
        message_gsm7 = 'A' * 100
        message_unicode = 'À' * 100  # Caractère hors GSM-7

        resp_gsm = self.client.post('/api/sms/preview/', {'content': message_gsm7}, format='json')
        resp_uni = self.client.post('/api/sms/preview/', {'content': message_unicode}, format='json')

        self.assertEqual(resp_gsm.status_code, 200)
        self.assertEqual(resp_uni.status_code, 200)
        self.assertEqual(resp_gsm.data['encoding'], 'GSM-7')
        self.assertEqual(resp_uni.data['encoding'], 'Unicode')
        # 100 chars GSM-7 = 1 SMS (limite 160), 100 chars Unicode = 2 SMS (limite 70)
        self.assertLess(resp_gsm.data['sms_count'], resp_uni.data['sms_count'])

    def test_preview_sans_content_ni_template_400(self):
        """Ni content ni template_id → 400."""
        resp = self.client.post('/api/sms/preview/', {}, format='json')
        self.assertEqual(resp.status_code, 400)


# ── SMSWebhookView ────────────────────────────────────────────────────────────

class TestSMSWebhookDelivered(TestCase):
    """
    Webhook SMS Partner — POST /api/sms/webhook/<token>/?messageId=X&status=1
    Met à jour le statut SMSLog de PENDING à DELIVERED.
    En test, SMS_WEBHOOK_SECRET n'est pas défini → token ignoré.
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy(credits=5)
        self.log = SMSLog.objects.create(
            pharmacy=self.pharmacy,
            to_hash='abc123',
            status=SMSLog.Status.PENDING,
            provider_message_id='SP-MSG-42',
            credits_used=1,
        )

    def test_webhook_status1_passe_en_delivered(self):
        """POST webhook avec status=1 (SMS Partner livré) → SMSLog.status = DELIVERED."""
        client = APIClient()
        resp = client.post(
            '/api/sms/webhook/any-token/',
            {'messageId': 'SP-MSG-42', 'status': 1},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.log.refresh_from_db()
        self.assertEqual(self.log.status, SMSLog.Status.DELIVERED)

    def test_webhook_status_non1_passe_en_failed(self):
        """POST webhook avec status≠1 → SMSLog.status = FAILED."""
        client = APIClient()
        resp = client.post(
            '/api/sms/webhook/any-token/',
            {'messageId': 'SP-MSG-42', 'status': 2},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.log.refresh_from_db()
        self.assertEqual(self.log.status, SMSLog.Status.FAILED)

    def test_webhook_msgid_inconnu_retourne_200(self):
        """Webhook avec messageId inexistant → 200 silencieux (pas d'erreur)."""
        client = APIClient()
        resp = client.post(
            '/api/sms/webhook/any-token/',
            {'messageId': 'INCONNU-9999', 'status': 1},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_webhook_sans_msgid_retourne_400(self):
        """Webhook sans messageId → 400."""
        client = APIClient()
        resp = client.post(
            '/api/sms/webhook/any-token/',
            {'status': 1},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_webhook_via_get_fonctionne_aussi(self):
        """SMS Partner peut envoyer en GET (query params) — les deux méthodes supportées."""
        client = APIClient()
        resp = client.get(
            '/api/sms/webhook/any-token/?messageId=SP-MSG-42&status=1',
        )
        self.assertEqual(resp.status_code, 200)
        self.log.refresh_from_db()
        self.assertEqual(self.log.status, SMSLog.Status.DELIVERED)
