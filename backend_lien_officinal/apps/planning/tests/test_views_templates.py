"""
Tests planning/views.py — TemplateApplyView, TemplateBulkReplaceView
"""

import datetime
from zoneinfo import ZoneInfo

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.core.models import Pharmacy
from apps.planning.models import AbsenceRequest, Shift, TemplateShift, WeekTemplate
from apps.team.models import Collaborator

TZ = ZoneInfo("Europe/Paris")
_counter = 0


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_vt_{_counter}@test.com",
        password="pass",
        nom_officine="Test",
    )


def _make_collab(pharmacy):
    c = Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name="Eve",
        last_name="Template",
        role=Collaborator.Role.PREPARATEUR,
        color="#556677",
        weekly_hours=35,
        can_manage_planning=True,
    )
    return c


def _collab_client(pharmacy, collab):
    client = APIClient()
    token = AccessToken.for_user(pharmacy)
    token['auth_type'] = 'collaborator'
    token['collaborator_id'] = collab.id
    token['can_manage_planning'] = True
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


def _make_template(pharmacy, letter='A'):
    template, _ = WeekTemplate.objects.get_or_create(pharmacy=pharmacy, letter=letter)
    return template


def _add_template_shift(template, collab, day_of_week=0, h_start='09:00', h_end='17:00'):
    return TemplateShift.objects.create(
        template=template,
        collaborator=collab,
        day_of_week=day_of_week,
        start_time=datetime.time(*map(int, h_start.split(':'))),
        end_time=datetime.time(*map(int, h_end.split(':'))),
    )


# ── TemplateApplyView — semaine vide ─────────────────────────────────────────

class TestTemplateApplyEmptyWeek(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)
        self.template = _make_template(self.pharmacy, 'A')
        # Lundi + mardi
        _add_template_shift(self.template, self.collab, day_of_week=0)
        _add_template_shift(self.template, self.collab, day_of_week=1)

    def test_semaine_vide_created_n_replaced_zero(self):
        resp = self.client.post('/api/planning/templates/A/apply/', {'week': '2026-W11'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['created'], 2)
        self.assertEqual(resp.data['replaced'], 0)
        self.assertEqual(resp.data['skipped'], 0)

    def test_shifts_crees_en_db(self):
        self.client.post('/api/planning/templates/A/apply/', {'week': '2026-W11'}, format='json')
        count = Shift.objects.filter(collaborator=self.collab).count()
        self.assertEqual(count, 2)

    def test_apply_sans_force_sur_semaine_pleine_skipped(self):
        """Deuxième apply sans force → skipped=2, pas de duplication."""
        self.client.post('/api/planning/templates/A/apply/', {'week': '2026-W11'}, format='json')
        resp = self.client.post('/api/planning/templates/A/apply/', {'week': '2026-W11'}, format='json')
        self.assertEqual(resp.data['skipped'], 2)
        self.assertEqual(Shift.objects.filter(collaborator=self.collab).count(), 2)

    def test_apply_avec_force_remplace(self):
        self.client.post('/api/planning/templates/A/apply/', {'week': '2026-W11'}, format='json')
        resp = self.client.post(
            '/api/planning/templates/A/apply/',
            {'week': '2026-W11', 'force': True},
            format='json',
        )
        self.assertEqual(resp.data['replaced'], 2)
        self.assertEqual(resp.data['created'], 2)
        self.assertEqual(Shift.objects.filter(collaborator=self.collab).count(), 2)


# ── TemplateApplyView — shift splitté (matin + après-midi) ───────────────────

class TestTemplateApplySplitShift(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)
        self.template = _make_template(self.pharmacy, 'B')
        # Deux TemplateShifts le même jour (lundi) = shift splitté
        _add_template_shift(self.template, self.collab, day_of_week=0, h_start='09:00', h_end='13:00')
        _add_template_shift(self.template, self.collab, day_of_week=0, h_start='14:00', h_end='18:00')

    def test_les_deux_shifts_crees(self):
        resp = self.client.post('/api/planning/templates/B/apply/', {'week': '2026-W11'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['created'], 2)
        self.assertEqual(resp.data['replaced'], 0)
        self.assertEqual(Shift.objects.filter(collaborator=self.collab).count(), 2)

    def test_deuxieme_apply_avec_force_remplace_les_deux(self):
        self.client.post('/api/planning/templates/B/apply/', {'week': '2026-W11'}, format='json')
        resp = self.client.post(
            '/api/planning/templates/B/apply/',
            {'week': '2026-W11', 'force': True},
            format='json',
        )
        # 1 seul "replaced" (la paire est comptée une fois), 2 créés
        self.assertEqual(resp.data['replaced'], 1)
        self.assertEqual(resp.data['created'], 2)
        self.assertEqual(Shift.objects.filter(collaborator=self.collab).count(), 2)


# ── TemplateApplyView — absence approuvée → shift ignoré ─────────────────────

class TestTemplateApplyAbsenceApproved(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)
        self.template = _make_template(self.pharmacy, 'A')
        _add_template_shift(self.template, self.collab, day_of_week=0)  # lundi
        # Absence approuvée sur lundi 9 mars 2026
        AbsenceRequest.objects.create(
            collaborator=self.collab,
            start_date=datetime.date(2026, 3, 9),
            end_date=datetime.date(2026, 3, 9),
            type=AbsenceRequest.AbsenceType.CP,
            status=AbsenceRequest.Status.APPROVED,
            start_period='morning',
            end_period='evening',
        )

    def test_shift_ignore_absence_protected(self):
        resp = self.client.post('/api/planning/templates/A/apply/', {'week': '2026-W11'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['absence_protected'], 1)
        self.assertEqual(resp.data['created'], 0)
        self.assertEqual(Shift.objects.filter(collaborator=self.collab).count(), 0)


# ── TemplateApplyView — absence en attente → shift créé quand même (🆕) ──────

class TestTemplateApplyAbsencePending(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)
        self.template = _make_template(self.pharmacy, 'A')
        _add_template_shift(self.template, self.collab, day_of_week=0)
        # Absence EN ATTENTE (non approuvée) sur lundi
        AbsenceRequest.objects.create(
            collaborator=self.collab,
            start_date=datetime.date(2026, 3, 9),
            end_date=datetime.date(2026, 3, 9),
            type=AbsenceRequest.AbsenceType.CP,
            status=AbsenceRequest.Status.PENDING,
            start_period='morning',
            end_period='evening',
        )

    def test_absence_pending_protege_aussi_le_shift(self):
        """Le code bloque aussi les absences PENDING (pas seulement APPROVED)."""
        resp = self.client.post('/api/planning/templates/A/apply/', {'week': '2026-W11'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['absence_protected'], 1)
        self.assertEqual(resp.data['created'], 0)


# ── TemplateApplyView — jour férié → shift ignoré ─────────────────────────────

class TestTemplateApplyFerie(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)
        self.template = _make_template(self.pharmacy, 'A')
        # Jeudi = day_of_week=3 → 6 avril 2026 = Lundi de Pâques (férié)
        # Semaine 2026-W14 : lundi 30 mars → dimanche 5 avril
        # Lundi de Pâques 2026 = 6 avril = semaine W15
        # W15 : lundi 6 avril (férié)
        _add_template_shift(self.template, self.collab, day_of_week=0)  # lundi

    def test_jour_ferie_ferie_skipped(self):
        # Semaine W15 2026 : lundi = 6 avril = Lundi de Pâques
        resp = self.client.post('/api/planning/templates/A/apply/', {'week': '2026-W15'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['ferie_skipped'], 1)
        self.assertEqual(resp.data['created'], 0)


# ── TemplateBulkReplaceView ───────────────────────────────────────────────────

class TestTemplateBulkReplace(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)

    def test_bulk_replace_cree_shifts(self):
        resp = self.client.post('/api/planning/templates/A/bulk-replace/', [
            {
                'collaborator_id': self.collab.id,
                'day_of_week': 0,
                'start_time': '09:00:00',
                'end_time': '17:00:00',
            },
            {
                'collaborator_id': self.collab.id,
                'day_of_week': 1,
                'start_time': '09:00:00',
                'end_time': '17:00:00',
            },
        ], format='json')
        self.assertIn(resp.status_code, [200, 201])
        template = WeekTemplate.objects.get(pharmacy=self.pharmacy, letter='A')
        self.assertEqual(template.shifts.count(), 2)

    def test_bulk_replace_remplace_anciens_shifts(self):
        """Un deuxième bulk-replace remplace complètement le template."""
        self.client.post('/api/planning/templates/A/bulk-replace/', [
            {'collaborator_id': self.collab.id, 'day_of_week': 0, 'start_time': '09:00:00', 'end_time': '17:00:00'},
            {'collaborator_id': self.collab.id, 'day_of_week': 1, 'start_time': '09:00:00', 'end_time': '17:00:00'},
        ], format='json')
        # Remplace avec seulement 1 shift
        self.client.post('/api/planning/templates/A/bulk-replace/', [
            {'collaborator_id': self.collab.id, 'day_of_week': 2, 'start_time': '09:00:00', 'end_time': '17:00:00'},
        ], format='json')
        template = WeekTemplate.objects.get(pharmacy=self.pharmacy, letter='A')
        self.assertEqual(template.shifts.count(), 1)
