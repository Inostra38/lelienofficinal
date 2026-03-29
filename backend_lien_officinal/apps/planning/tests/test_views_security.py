"""
Tests planning/views.py — Sécurité avancée (Phase 3)
- PayeAnalyticsView → 403 sans can_manage_planning
- TemplateBulkReplaceView → isolation inter-pharmacie
- Injection query param ?pharmacy_id ignorée
- PATCH shift inexistant → 404
"""

import datetime

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.core.models import Pharmacy
from apps.planning.models import Shift
from apps.team.models import Collaborator

_counter = 0


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_sec_{_counter}@test.com",
        password="pass",
        nom_officine="Test",
    )


_collab_counter = 0

def _make_collab(pharmacy, can_manage=True):
    global _collab_counter
    _collab_counter += 1
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name=f"Frank{_collab_counter}",
        last_name="Security",
        role=Collaborator.Role.PREPARATEUR,
        color="#aabbcc",
        weekly_hours=35,
        can_manage_planning=can_manage,
    )


def _collab_client(pharmacy, collab):
    client = APIClient()
    token = AccessToken.for_user(pharmacy)
    token['auth_type'] = 'collaborator'
    token['collaborator_id'] = collab.id
    token['can_manage_planning'] = collab.can_manage_planning
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


def _pharmacy_client(pharmacy):
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def _make_shift(collab, d=None):
    d = d or datetime.date(2026, 3, 9)
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Paris")
    return Shift.objects.create(
        collaborator=collab,
        start_datetime=datetime.datetime(d.year, d.month, d.day, 9, 0, tzinfo=tz),
        end_datetime=datetime.datetime(d.year, d.month, d.day, 17, 0, tzinfo=tz),
        is_published=False,
    )


# ── PayeAnalyticsView — 403 sans can_manage_planning ─────────────────────────

class TestPayeAnalyticsPermission(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.manager = _make_collab(self.pharmacy, can_manage=True)
        self.preparateur = _make_collab(self.pharmacy, can_manage=False)
        self.preparateur.first_name = "Paul"
        self.preparateur.save()

    def test_sans_collaborateur_token_403(self):
        """Token pharmacie seul (pas de collaborator_id) → 403."""
        client = _pharmacy_client(self.pharmacy)
        resp = client.get('/api/planning/analytics/paie/?month=2026-03')
        self.assertEqual(resp.status_code, 403)

    def test_collab_sans_permission_403(self):
        client = _collab_client(self.pharmacy, self.preparateur)
        resp = client.get('/api/planning/analytics/paie/?month=2026-03')
        self.assertEqual(resp.status_code, 403)

    def test_manager_avec_permission_200(self):
        client = _collab_client(self.pharmacy, self.manager)
        resp = client.get('/api/planning/analytics/paie/?month=2026-03')
        self.assertEqual(resp.status_code, 200)

    def test_month_manquant_400(self):
        client = _collab_client(self.pharmacy, self.manager)
        resp = client.get('/api/planning/analytics/paie/')
        self.assertEqual(resp.status_code, 400)


# ── Isolation inter-pharmacie — shift d'une autre pharmacie ──────────────────

class TestShiftIsolation(TestCase):

    def setUp(self):
        self.pharmacy_a = _make_pharmacy()
        self.pharmacy_b = _make_pharmacy()
        self.collab_a = _make_collab(self.pharmacy_a)
        self.collab_b = _make_collab(self.pharmacy_b)
        self.shift_b = _make_shift(self.collab_b)
        self.client_a = _collab_client(self.pharmacy_a, self.collab_a)

    def test_patch_shift_autre_pharmacie_404(self):
        resp = self.client_a.patch(
            f'/api/planning/shifts/{self.shift_b.pk}/',
            {'note': 'injection'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_shift_autre_pharmacie_404(self):
        resp = self.client_a.delete(f'/api/planning/shifts/{self.shift_b.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_get_shift_autre_pharmacie_404(self):
        resp = self.client_a.get(f'/api/planning/shifts/{self.shift_b.pk}/')
        self.assertEqual(resp.status_code, 404)


# ── Injection via query param ?pharmacy_id ignorée ────────────────────────────

class TestQueryParamInjection(TestCase):
    """
    Un acteur malveillant envoie ?pharmacy_id=<id_autre_pharmacie>.
    La vue doit ignorer ce paramètre et n'utiliser que la pharmacie du token.
    """

    def setUp(self):
        self.pharmacy_a = _make_pharmacy()
        self.pharmacy_b = _make_pharmacy()
        self.collab_a = _make_collab(self.pharmacy_a)
        self.collab_b = _make_collab(self.pharmacy_b)
        self.shift_b = _make_shift(self.collab_b)
        self.client_a = _collab_client(self.pharmacy_a, self.collab_a)

    def test_week_view_pharmacy_id_param_ignore(self):
        """GET /planning/week/?pharmacy_id=<autre> → données de la pharmacie du token seulement."""
        self.client_a.post('/api/planning/shifts/', {
            'collaborator_id': self.collab_a.id,
            'start_datetime': '2026-03-09T09:00:00+01:00',
            'end_datetime':   '2026-03-09T17:00:00+01:00',
        }, format='json')
        resp = self.client_a.get(
            f'/api/planning/week/?week=2026-W11&pharmacy_id={self.pharmacy_b.pk}'
        )
        self.assertEqual(resp.status_code, 200)
        # Aucun shift de la pharmacie B ne doit apparaître
        all_shift_ids = [
            s['id']
            for collab_data in resp.data.get('collaborators', [])
            for s in collab_data.get('shifts', [])
        ]
        self.assertNotIn(self.shift_b.pk, all_shift_ids)

    def test_template_apply_autre_pharmacie_collaborateur_rejete(self):
        """TemplateApplyView avec un collaborateur_id d'une autre pharmacie → shift pas créé."""
        from apps.planning.models import WeekTemplate, TemplateShift
        template, _ = WeekTemplate.objects.get_or_create(pharmacy=self.pharmacy_a, letter='A')
        # Injecter un TemplateShift pointant vers le collaborateur de la pharmacie B
        TemplateShift.objects.create(
            template=template,
            collaborator=self.collab_b,   # appartient à pharmacy_b !
            day_of_week=0,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(17, 0),
        )
        resp = self.client_a.post('/api/planning/templates/A/apply/', {'week': '2026-W11'}, format='json')
        self.assertEqual(resp.status_code, 200)
        # Le shift du collab_b ne doit pas être créé dans la pharmacie A
        self.assertEqual(
            Shift.objects.filter(collaborator=self.collab_b).count(), 1  # seulement le setUp
        )


# ── PATCH sur ressource inexistante → 404 ─────────────────────────────────────

class TestPatchNonExistent(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)

    def test_patch_shift_inexistant_404(self):
        resp = self.client.patch('/api/planning/shifts/99999/', {'note': 'x'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_delete_shift_inexistant_404(self):
        resp = self.client.delete('/api/planning/shifts/99999/')
        self.assertEqual(resp.status_code, 404)
