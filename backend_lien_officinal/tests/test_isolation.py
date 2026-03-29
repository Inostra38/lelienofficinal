"""
Tests d'isolation inter-pharmacie (ownership).

Vérifie qu'aucune donnée d'une pharmacie n'est accessible
depuis une autre pharmacie, quel que soit l'endpoint.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.core.models import Pharmacy
from apps.messaging.models import Conversation
from apps.planning.models import Shift
from apps.quality.models import Procedure
from apps.team.models import Collaborator

TZ = ZoneInfo("Europe/Paris")
_counter = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"iso_{_counter}@test.com",
        password="pass",
        nom_officine=f"Pharmacie Iso {_counter}",
    )


def _make_collab(pharmacy, n=0):
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name=f"Collab{n}",
        last_name="Iso",
        role=Collaborator.Role.PREPARATEUR,
        color="#123456",
        weekly_hours=35,
        can_manage_planning=True,
    )


def _make_shift(collab, day=None):
    d = day or date(2026, 3, 9)
    return Shift.objects.create(
        collaborator=collab,
        start_datetime=datetime(d.year, d.month, d.day, 9, 0, tzinfo=TZ),
        end_datetime=datetime(d.year, d.month, d.day, 17, 0, tzinfo=TZ),
        is_published=True,
    )


def _pharmacy_client(pharmacy):
    """Token JWT pharmacie directe (sans collaborateur dans le token)."""
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def _collab_client(pharmacy, collab):
    """Token JWT avec collaborateur embarqué (auth_type=collaborator)."""
    client = APIClient()
    token = AccessToken.for_user(pharmacy)
    token['auth_type'] = 'collaborator'
    token['collaborator_id'] = collab.id
    token['can_manage_planning'] = collab.can_manage_planning
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


# ── Planning — shifts ─────────────────────────────────────────────────────────

class TestIsolationPlanningShifts(TestCase):
    """
    Pharmacie A ne peut pas voir, modifier ni supprimer les shifts de pharmacie B.
    """

    def setUp(self):
        self.ph_a = _make_pharmacy()
        self.ph_b = _make_pharmacy()
        self.collab_a = _make_collab(self.ph_a, 1)
        self.collab_b = _make_collab(self.ph_b, 2)
        self.shift_a = _make_shift(self.collab_a)
        self.shift_b = _make_shift(self.collab_b)
        self.client_a = _pharmacy_client(self.ph_a)

    def test_get_week_ne_voit_pas_shifts_de_b(self):
        """GET /api/planning/week/ retourne uniquement les shifts de la pharmacie du token."""
        resp = self.client_a.get('/api/planning/week/?week=2026-W11')
        self.assertEqual(resp.status_code, 200)
        # WeekView retourne {'summary': [...], 'shifts': [...], ...}
        # 'shifts' = liste plate des shifts bruts ; 'summary' = résumé par collaborateur
        shift_ids_flat = [s['id'] for s in resp.data.get('shifts', [])]
        self.assertIn(self.shift_a.id, shift_ids_flat)
        self.assertNotIn(self.shift_b.id, shift_ids_flat)

    def test_patch_shift_autre_pharmacie_404(self):
        """PATCH sur un shift appartenant à B → 404, pas d'accès."""
        resp = self.client_a.patch(
            f'/api/planning/shifts/{self.shift_b.id}/',
            {'note': 'tentative de modification'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_shift_autre_pharmacie_404(self):
        """DELETE sur un shift appartenant à B → 404, le shift B reste intact."""
        resp = self.client_a.delete(f'/api/planning/shifts/{self.shift_b.id}/')
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Shift.objects.filter(pk=self.shift_b.pk).exists())

    def test_post_shift_avec_collaborateur_autre_pharmacie_400(self):
        """
        POST /api/planning/shifts/ avec collaborator_id appartenant à B →
        le serializer rejette (Collaborateur introuvable) avec un 400.
        Aucun shift supplémentaire ne doit être créé pour le collab de B.
        """
        resp = self.client_a.post(
            '/api/planning/shifts/',
            {
                'collaborator_id': self.collab_b.id,
                'start_datetime': '2026-03-09T09:00:00+01:00',
                'end_datetime': '2026-03-09T17:00:00+01:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Shift.objects.filter(collaborator=self.collab_b).count(), 1)  # seulement le shift setUp


# ── Qualité — procédures ──────────────────────────────────────────────────────

class TestIsolationQualiteProcedures(TestCase):
    """
    Pharmacie A ne peut pas lire les procédures de pharmacie B.
    """

    def setUp(self):
        self.ph_a = _make_pharmacy()
        self.ph_b = _make_pharmacy()
        self.proc_b = Procedure.objects.create(
            pharmacy=self.ph_b,
            title='Procédure confidentielle B',
            content='Contenu B',
        )
        self.client_a = _pharmacy_client(self.ph_a)

    def test_get_procedure_autre_pharmacie_404(self):
        """GET /api/quality/procedures/{id}/ d'une proc appartenant à B → 404."""
        resp = self.client_a.get(f'/api/quality/procedures/{self.proc_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_list_procedures_ne_voit_pas_pharmacie_b(self):
        """GET /api/quality/procedures/ ne liste que les procédures de la pharmacie du token."""
        resp = self.client_a.get('/api/quality/procedures/')
        self.assertEqual(resp.status_code, 200)
        # ProcedureViewSet retourne une liste directe (pas de pagination)
        ids = [p['id'] for p in resp.data]
        self.assertNotIn(self.proc_b.id, ids)


# ── Messagerie — conversations ────────────────────────────────────────────────

class TestIsolationMessagingConversations(TestCase):
    """
    Un collaborateur de pharmacie A ne peut pas accéder à une conversation de pharmacie B.
    """

    def setUp(self):
        self.ph_a = _make_pharmacy()
        self.ph_b = _make_pharmacy()
        self.collab_a = _make_collab(self.ph_a, 1)
        collab_b1 = _make_collab(self.ph_b, 2)
        collab_b2 = _make_collab(self.ph_b, 3)
        # Conversation appartenant à la pharmacie B
        self.conv_b = Conversation.objects.create(pharmacy=self.ph_b, subject='Conv B')
        self.conv_b.participants.set([collab_b1, collab_b2])
        # Client : collab de A (JWT auth_type=collaborator requis par ConversationDetailView)
        self.client_a = _collab_client(self.ph_a, self.collab_a)

    def test_get_conversation_autre_pharmacie_404(self):
        """GET /api/messaging/conversations/{uuid}/ appartenant à B → 404."""
        resp = self.client_a.get(f'/api/messaging/conversations/{self.conv_b.id}/')
        self.assertEqual(resp.status_code, 404)


# ── Équipe — collab d'une autre pharmacie ─────────────────────────────────────

class TestIsolationTeamCollab(TestCase):
    """
    Les actions 'login' et 'verify-pin' avec un ID de collab d'une autre pharmacie
    ne doivent pas réussir — le filtre pharmacy=request.user les bloque.
    """

    def setUp(self):
        self.ph_a = _make_pharmacy()
        self.ph_b = _make_pharmacy()
        self.collab_b = _make_collab(self.ph_b, 1)
        self.collab_b.set_pin('1234')
        self.collab_b.save()
        self.client_a = _pharmacy_client(self.ph_a)

    def test_login_collab_autre_pharmacie_404(self):
        """POST /api/team/login/ avec collab appartenant à B → 404 même si le PIN est correct."""
        resp = self.client_a.post(
            '/api/team/login/',
            {'collaborator_id': self.collab_b.id, 'pin_code': '1234'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_verify_pin_collab_autre_pharmacie_404(self):
        """POST /api/team/verify-pin/ avec collab de B → 404."""
        resp = self.client_a.post(
            '/api/team/verify-pin/',
            {'collaborator_id': self.collab_b.id, 'pin_code': '1234'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_equipe_ne_voit_pas_collaborateurs_de_b(self):
        """GET /api/team/ ne retourne que les collaborateurs de la pharmacie du token."""
        resp = self.client_a.get('/api/team/')
        self.assertEqual(resp.status_code, 200)
        collab_ids = [c['id'] for c in resp.data]
        self.assertNotIn(self.collab_b.id, collab_ids)

    def test_get_collab_detail_autre_pharmacie_404(self):
        """GET /api/team/{id}/ d'un collab appartenant à B → 404."""
        resp = self.client_a.get(f'/api/team/{self.collab_b.id}/')
        self.assertEqual(resp.status_code, 404)
