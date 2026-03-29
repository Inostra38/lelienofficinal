"""
Tests planning/views.py — ShiftDetailView (PATCH collision), cross-midnight,
PublishWeekView (snapshot, idempotent), SplitShiftView
"""

import datetime
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.core.models import Pharmacy
from apps.planning.models import Shift
from apps.team.models import Collaborator

TZ = ZoneInfo("Europe/Paris")
_counter = 0


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_vs_{_counter}@test.com",
        password="pass",
        nom_officine="Test",
    )


def _make_collab(pharmacy, can_manage=True):
    c = Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name="Carl",
        last_name="Shift",
        role=Collaborator.Role.PREPARATEUR,
        color="#334455",
        weekly_hours=35,
    )
    if can_manage:
        c.can_manage_planning = True
        c.save(update_fields=["can_manage_planning"])
    return c


def _pharmacy_client(pharmacy):
    """Client authentifié avec le JWT pharmacie (pas collaborateur)."""
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def _collab_client(pharmacy, collab):
    """Client avec un JWT collaborateur (auth_type=collaborator)."""
    client = APIClient()
    token = AccessToken.for_user(pharmacy)
    token['auth_type'] = 'collaborator'
    token['collaborator_id'] = collab.id
    token['can_manage_planning'] = collab.can_manage_planning
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


def _dt(d: datetime.date, h: int, m: int = 0) -> datetime.datetime:
    return datetime.datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)


def _make_shift(collab, d: datetime.date, h_start=9, h_end=17):
    return Shift.objects.create(
        collaborator=collab,
        start_datetime=_dt(d, h_start),
        end_datetime=_dt(d, h_end),
        is_published=False,
    )


# ── ShiftDetailView PATCH — collision detection ───────────────────────────────

class TestShiftPatchCollision(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)
        d = datetime.date(2026, 3, 9)
        self.shift = _make_shift(self.collab, d)

    def test_patch_sans_updated_at_reussit(self):
        resp = self.client.patch(
            f'/api/planning/shifts/{self.shift.pk}/',
            {'note': 'ok'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_patch_updated_at_correct_reussit(self):
        self.shift.refresh_from_db()
        resp = self.client.patch(
            f'/api/planning/shifts/{self.shift.pk}/',
            {'note': 'ok', 'updated_at': self.shift.updated_at.isoformat()},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_patch_updated_at_obsolete_409(self):
        old_ts = (self.shift.updated_at - datetime.timedelta(minutes=5)).isoformat()
        resp = self.client.patch(
            f'/api/planning/shifts/{self.shift.pk}/',
            {'note': 'conflit', 'updated_at': old_ts},
            format='json',
        )
        self.assertEqual(resp.status_code, 409)

    def test_patch_shift_inconnu_404(self):
        resp = self.client.patch('/api/planning/shifts/99999/', {'note': 'x'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_patch_shift_autre_pharmacie_404(self):
        other = _make_pharmacy()
        other_collab = _make_collab(other)
        other_shift = _make_shift(other_collab, datetime.date(2026, 3, 9))
        resp = self.client.patch(
            f'/api/planning/shifts/{other_shift.pk}/',
            {'note': 'hack'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)


# ── Création shift cross-midnight ─────────────────────────────────────────────

class TestShiftCrossMidnight(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)

    def test_shift_cross_midnight_cree(self):
        """Un shift 22h → 06h (lendemain) doit être accepté."""
        resp = self.client.post('/api/planning/shifts/', {
            'collaborator_id': self.collab.id,
            'start_datetime': '2026-03-09T22:00:00+01:00',
            'end_datetime':   '2026-03-10T06:00:00+01:00',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        shift = Shift.objects.get(pk=resp.data['id'])
        self.assertNotEqual(
            shift.start_datetime.date(),
            shift.end_datetime.date(),
        )

    def test_shift_end_avant_start_rejete(self):
        """end_datetime < start_datetime → CheckConstraint → la vue retourne une erreur (400 ou 500)."""
        self.client.raise_request_exception = False
        resp = self.client.post('/api/planning/shifts/', {
            'collaborator_id': self.collab.id,
            'start_datetime': '2026-03-09T17:00:00+01:00',
            'end_datetime':   '2026-03-09T09:00:00+01:00',
        }, format='json')
        self.assertIn(resp.status_code, [400, 500])


# ── PublishWeekView ───────────────────────────────────────────────────────────

class TestPublishWeekView(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)
        d = datetime.date(2026, 3, 9)
        self.shift = _make_shift(self.collab, d)

    def test_publish_week_publie_shifts(self):
        resp = self.client.post('/api/planning/publish-week/', {'week': '2026-W11'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['published'], 1)
        self.shift.refresh_from_db()
        self.assertTrue(self.shift.is_published)

    def test_publish_week_snapshot_nom(self):
        """PublishWeekView capture le nom du collaborateur dans collaborator_snapshot."""
        self.client.post('/api/planning/publish-week/', {'week': '2026-W11'}, format='json')
        self.shift.refresh_from_db()
        self.assertIn('Carl', self.shift.collaborator_snapshot)
        self.assertIn('Shift', self.shift.collaborator_snapshot)

    def test_publish_week_idempotent(self):
        """Publier une semaine déjà publiée retourne published=0 sans erreur."""
        self.shift.is_published = True
        self.shift.save(update_fields=['is_published'])
        resp = self.client.post('/api/planning/publish-week/', {'week': '2026-W11'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['published'], 0)

    def test_publish_week_sans_shifts_published_zero(self):
        Shift.objects.filter(collaborator=self.collab).delete()
        resp = self.client.post('/api/planning/publish-week/', {'week': '2026-W11'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['published'], 0)


# ── SplitShiftView ────────────────────────────────────────────────────────────

class TestSplitShiftView(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)
        d = datetime.date(2026, 3, 9)
        self.shift = _make_shift(self.collab, d, h_start=9, h_end=17)

    def test_split_correct_deux_shifts(self):
        resp = self.client.post(
            f'/api/planning/shifts/{self.shift.pk}/split/',
            {'split_time': '13:00'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn('shift_1', resp.data)
        self.assertIn('shift_2', resp.data)
        # Shift original supprimé
        self.assertFalse(Shift.objects.filter(pk=self.shift.pk).exists())
        # 2 nouveaux shifts créés
        self.assertEqual(Shift.objects.filter(collaborator=self.collab).count(), 2)

    def test_split_heures_coherentes(self):
        resp = self.client.post(
            f'/api/planning/shifts/{self.shift.pk}/split/',
            {'split_time': '13:00'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        s1 = resp.data['shift_1']
        s2 = resp.data['shift_2']
        # shift_1 : 09:00 → 13:00 ; shift_2 : 13:00 → 17:00
        self.assertIn('13:00', s1['end_datetime'])
        self.assertIn('13:00', s2['start_datetime'])

    def test_split_coupure_apres_fin_400(self):
        """Coupure après la fin du shift → 400."""
        resp = self.client.post(
            f'/api/planning/shifts/{self.shift.pk}/split/',
            {'split_time': '18:00'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_split_format_invalide_400(self):
        resp = self.client.post(
            f'/api/planning/shifts/{self.shift.pk}/split/',
            {'split_time': 'pas-une-heure'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_split_shift_inconnu_404(self):
        resp = self.client.post(
            '/api/planning/shifts/99999/split/',
            {'split_time': '13:00'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)
