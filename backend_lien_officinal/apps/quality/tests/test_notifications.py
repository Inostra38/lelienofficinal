"""
Tests ProcedureNotificationViewSet.

- Pharmacie sans collaborateur JWT → liste vide (aucun collaborator_id dans le token)
- Collaborateur avec notifications → unread_count correct, entrées retournées
- Isolation : un collaborateur d'une autre pharmacie ne voit pas ces notifications
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy
from apps.quality.models import Procedure, ProcedureNotification
from apps.team.models import Collaborator

_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"notif_{_counter}@test.com",
        password="pass",
        nom_officine="Pharmacie Notif",
    )


def _make_collab(pharmacy):
    global _counter
    _counter += 1
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name=f"Collab{_counter}",
        last_name="Notif",
        role=Collaborator.Role.PREPARATEUR,
        color="#aabbcc",
        weekly_hours=35,
    )


def _pharmacy_client(pharmacy):
    """JWT pharmacie directe — pas de collaborator_id."""
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def _collab_client(pharmacy, collab_id):
    """JWT collaborateur — contient collaborator_id dans les claims."""
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    refresh['collaborator_id'] = collab_id
    refresh['auth_type'] = 'collaborator'
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def _make_procedure(pharmacy):
    return Procedure.objects.create(
        pharmacy=pharmacy,
        title="Procédure notif",
        content="Contenu",
    )


def _make_notification(collab, procedure, is_read=False):
    return ProcedureNotification.objects.create(
        recipient=collab,
        procedure=procedure,
        version_number=1,
        is_read=is_read,
    )


class TestNotificationListPharmacieJWT(TestCase):
    """Avec un JWT pharmacie (sans collaborator_id) → liste vide."""

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.proc = _make_procedure(self.pharmacy)
        _make_notification(self.collab, self.proc)
        self.client = _pharmacy_client(self.pharmacy)

    def test_liste_vide_sans_collaborateur_jwt(self):
        resp = self.client.get('/api/quality/notifications/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['results'], [])
        self.assertEqual(resp.data['unread_count'], 0)


class TestNotificationListCollabJWT(TestCase):
    """Avec un JWT collaborateur → notifications retournées, unread_count correct."""

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.proc = _make_procedure(self.pharmacy)
        # 2 non lues + 1 lue
        _make_notification(self.collab, self.proc, is_read=False)
        _make_notification(self.collab, self.proc, is_read=False)
        _make_notification(self.collab, self.proc, is_read=True)
        self.client = _collab_client(self.pharmacy, self.collab.id)

    def test_trois_notifications_retournees(self):
        resp = self.client.get('/api/quality/notifications/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 3)

    def test_unread_count_deux(self):
        resp = self.client.get('/api/quality/notifications/')
        self.assertEqual(resp.data['unread_count'], 2)


class TestNotificationIsolation(TestCase):
    """Un collaborateur d'une autre pharmacie ne voit pas les notifications d'ici."""

    def setUp(self):
        self.pharmacy_a = _make_pharmacy()
        self.pharmacy_b = _make_pharmacy()
        self.collab_a = _make_collab(self.pharmacy_a)
        self.collab_b = _make_collab(self.pharmacy_b)
        self.proc_a = _make_procedure(self.pharmacy_a)
        # Notif pour collab_a dans pharmacy_a
        _make_notification(self.collab_a, self.proc_a)
        # Client de pharmacy_b avec son propre collab_b
        self.client_b = _collab_client(self.pharmacy_b, self.collab_b.id)

    def test_collab_autre_pharmacie_voit_zero_notification(self):
        """collab_b ne doit pas voir les notifications de collab_a (autre pharmacie)."""
        resp = self.client_b.get('/api/quality/notifications/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['results'], [])
        self.assertEqual(resp.data['unread_count'], 0)
