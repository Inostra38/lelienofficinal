"""
Tests NonConformityViewSet — workflow OPEN→IN_PROGRESS→CLOSED, transitions invalides.
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy
from apps.quality.models import NonConformity
from apps.team.models import Collaborator

_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"nc_{_counter}@test.com",
        password="pass",
        nom_officine="Test NC",
    )


def _make_collab(pharmacy):
    global _counter
    _counter += 1
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name=f"Collab{_counter}",
        last_name="NC",
        role=Collaborator.Role.PREPARATEUR,
        color="#aabbcc",
        weekly_hours=35,
    )


def _pharmacy_client(pharmacy):
    """Token pharmacie directe → passe tous les checks de permissions qualité."""
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def _make_nc(pharmacy):
    return NonConformity.objects.create(
        pharmacy=pharmacy,
        title="NC test",
        description="Description test",
        severity=NonConformity.Severity.MINOR,
    )


# ── Workflow principal ────────────────────────────────────────────────────────

class TestNCWorkflow(TestCase):
    """Workflow complet OPEN → IN_PROGRESS → CLOSED."""

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _pharmacy_client(self.pharmacy)

    def test_creation_statut_open(self):
        """POST /api/quality/nonconformities/ → 201, statut OPEN par défaut."""
        resp = self.client.post(
            '/api/quality/nonconformities/',
            {
                'title': 'NC création',
                'description': 'Problème détecté',
                'severity': 'minor',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['status'], 'open')

    def test_assign_passe_en_in_progress(self):
        """POST assign → status IN_PROGRESS, assigned_to positionné."""
        nc = _make_nc(self.pharmacy)
        resp = self.client.post(
            f'/api/quality/nonconformities/{nc.id}/assign/',
            {'assigned_to': self.collab.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'in_progress')
        self.assertEqual(resp.data['assigned_to']['id'], self.collab.id)

    def test_close_depuis_in_progress_ok(self):
        """Close sur NC IN_PROGRESS → CLOSED, closed_at renseigné."""
        nc = _make_nc(self.pharmacy)
        # D'abord assigner
        self.client.post(
            f'/api/quality/nonconformities/{nc.id}/assign/',
            {'assigned_to': self.collab.id},
            format='json',
        )
        resp = self.client.post(
            f'/api/quality/nonconformities/{nc.id}/close/',
            {'resolution': 'Problème résolu'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'closed')
        self.assertIsNotNone(resp.data['closed_at'])

    def test_reopen_depuis_closed_ok(self):
        """Reopen sur NC CLOSED → OPEN, closed_at effacé."""
        nc = _make_nc(self.pharmacy)
        nc.status = NonConformity.Status.IN_PROGRESS
        nc.save()
        self.client.post(f'/api/quality/nonconformities/{nc.id}/close/', {}, format='json')
        resp = self.client.post(f'/api/quality/nonconformities/{nc.id}/reopen/', {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'open')
        self.assertIsNone(resp.data['closed_at'])


# ── Transitions invalides ─────────────────────────────────────────────────────

class TestNCTransitionsInvalides(TestCase):
    """Transitions de statut interdites → 400."""

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _pharmacy_client(self.pharmacy)

    def test_close_depuis_open_400(self):
        """Close sur NC OPEN (non assignée) → 400."""
        nc = _make_nc(self.pharmacy)
        self.assertEqual(nc.status, NonConformity.Status.OPEN)
        resp = self.client.post(
            f'/api/quality/nonconformities/{nc.id}/close/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        # La NC reste OPEN
        nc.refresh_from_db()
        self.assertEqual(nc.status, NonConformity.Status.OPEN)

    def test_reopen_depuis_in_progress_400(self):
        """Reopen sur NC IN_PROGRESS (pas CLOSED) → 400."""
        nc = _make_nc(self.pharmacy)
        nc.status = NonConformity.Status.IN_PROGRESS
        nc.save()
        resp = self.client.post(
            f'/api/quality/nonconformities/{nc.id}/reopen/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_assign_sans_assigned_to_400(self):
        """POST assign sans le champ assigned_to → 400."""
        nc = _make_nc(self.pharmacy)
        resp = self.client.post(
            f'/api/quality/nonconformities/{nc.id}/assign/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_assign_collab_autre_pharmacie_404(self):
        """POST assign avec collab d'une autre pharmacie → 404."""
        nc = _make_nc(self.pharmacy)
        other_pharmacy = _make_pharmacy()
        other_collab = _make_collab(other_pharmacy)
        resp = self.client.post(
            f'/api/quality/nonconformities/{nc.id}/assign/',
            {'assigned_to': other_collab.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)
