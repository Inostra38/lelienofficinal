"""
Tests team/views.py — collaborator_login (avec lockout) et verify_pin
"""

import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy
from apps.team.models import Collaborator

_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_tv_{_counter}@test.com",
        password="pass",
        nom_officine="Test",
    )


def _make_collab(pharmacy, pin="1234", active=True):
    c = Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name="Bob",
        last_name="Test",
        role=Collaborator.Role.PREPARATEUR,
        color="#112233",
        weekly_hours=35,
        is_active=active,
    )
    c.set_pin(pin)
    c.save()
    return c


def _auth_client(pharmacy):
    """Retourne un APIClient authentifié avec le JWT de la pharmacie."""
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


# ── verify-pin (simple, sans lockout) ────────────────────────────────────────

class TestVerifyPin(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, pin="1234")
        self.client = _auth_client(self.pharmacy)

    def test_pin_correct_200(self):
        resp = self.client.post('/api/team/verify-pin/', {
            'collaborator_id': self.collab.id,
            'pin_code': '1234',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['success'])

    def test_pin_incorrect_403(self):
        resp = self.client.post('/api/team/verify-pin/', {
            'collaborator_id': self.collab.id,
            'pin_code': '9999',
        })
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.data['success'])

    def test_collaborateur_inconnu_404(self):
        resp = self.client.post('/api/team/verify-pin/', {
            'collaborator_id': 99999,
            'pin_code': '1234',
        })
        self.assertEqual(resp.status_code, 404)

    def test_sans_token_401(self):
        client = APIClient()
        resp = client.post('/api/team/verify-pin/', {
            'collaborator_id': self.collab.id,
            'pin_code': '1234',
        })
        self.assertEqual(resp.status_code, 401)


# ── collaborator_login (avec lockout complet) ─────────────────────────────────

class TestCollaboratorLogin(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, pin="5678")
        self.client = _auth_client(self.pharmacy)

    def test_login_correct_retourne_token(self):
        resp = self.client.post('/api/team/login/', {
            'collaborator_id': self.collab.id,
            'pin_code': '5678',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)

    def test_pin_incorrect_403(self):
        resp = self.client.post('/api/team/login/', {
            'collaborator_id': self.collab.id,
            'pin_code': '0000',
        })
        self.assertEqual(resp.status_code, 403)

    def test_pin_incorrect_incremente_fail_count(self):
        self.client.post('/api/team/login/', {
            'collaborator_id': self.collab.id,
            'pin_code': '0000',
        })
        self.collab.refresh_from_db()
        self.assertEqual(self.collab.pin_fail_count, 1)

    def test_compte_verouille_423(self):
        self.collab.pin_locked_until = timezone.now() + datetime.timedelta(hours=1)
        self.collab.save(update_fields=['pin_locked_until'])
        resp = self.client.post('/api/team/login/', {
            'collaborator_id': self.collab.id,
            'pin_code': '5678',
        })
        self.assertEqual(resp.status_code, 423)

    def test_login_succes_reset_fail_count(self):
        self.collab.pin_fail_count = 5
        self.collab.save(update_fields=['pin_fail_count'])
        self.client.post('/api/team/login/', {
            'collaborator_id': self.collab.id,
            'pin_code': '5678',
        })
        self.collab.refresh_from_db()
        self.assertEqual(self.collab.pin_fail_count, 0)

    def test_collaborateur_autre_pharmacie_404(self):
        other_pharmacy = _make_pharmacy()
        other_collab = _make_collab(other_pharmacy, pin="1111")
        resp = self.client.post('/api/team/login/', {
            'collaborator_id': other_collab.id,
            'pin_code': '1111',
        })
        # Collaborateur d'une autre pharmacie → 404
        self.assertEqual(resp.status_code, 404)

    def test_lockout_apres_50_echecs(self):
        """À 50 échecs consécutifs, le compte est verrouillé 24h."""
        self.collab.pin_fail_count = 49
        self.collab.save(update_fields=['pin_fail_count'])
        # 50e tentative incorrecte
        self.client.post('/api/team/login/', {
            'collaborator_id': self.collab.id,
            'pin_code': '0000',
        })
        self.collab.refresh_from_db()
        self.assertIsNotNone(self.collab.pin_locked_until)
        self.assertTrue(self.collab.pin_locked_until > timezone.now())
