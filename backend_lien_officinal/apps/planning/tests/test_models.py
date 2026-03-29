"""
Tests planning/models.py — Shift.save() snapshot, TimeAdjustment CheckConstraint
"""

import datetime
from zoneinfo import ZoneInfo

from django.db import IntegrityError
from django.test import TestCase

from apps.core.models import Pharmacy
from apps.planning.models import Shift, TimeAdjustment
from apps.team.models import Collaborator

TZ = ZoneInfo("Europe/Paris")
_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_pm_{_counter}@test.com",
        password="pass",
        nom_officine="Test",
    )


def _make_collab(pharmacy, weekly_hours=35.0):
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name="Gina",
        last_name="Model",
        role=Collaborator.Role.PREPARATEUR,
        color="#001122",
        weekly_hours=weekly_hours,
    )


def _dt(d: datetime.date, h: int) -> datetime.datetime:
    return datetime.datetime(d.year, d.month, d.day, h, 0, tzinfo=TZ)


# ── Shift.save() — contract_hours_snapshot ────────────────────────────────────

class TestShiftContractSnapshot(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, weekly_hours=35.0)
        self.d = datetime.date(2026, 3, 9)

    def test_snapshot_capture_a_la_creation(self):
        """contract_hours_snapshot est capturé automatiquement lors de la création."""
        shift = Shift.objects.create(
            collaborator=self.collab,
            start_datetime=_dt(self.d, 9),
            end_datetime=_dt(self.d, 17),
        )
        self.assertEqual(float(shift.contract_hours_snapshot), 35.0)

    def test_snapshot_non_modifie_si_contrat_change(self):
        """Modifier weekly_hours après création ne change pas le snapshot du shift."""
        shift = Shift.objects.create(
            collaborator=self.collab,
            start_datetime=_dt(self.d, 9),
            end_datetime=_dt(self.d, 17),
        )
        self.collab.weekly_hours = 28.0
        self.collab.save(update_fields=['weekly_hours'])
        shift.note = "modifié"
        shift.save(update_fields=['note'])
        shift.refresh_from_db()
        self.assertEqual(float(shift.contract_hours_snapshot), 35.0)

    def test_snapshot_explicite_preserve(self):
        """Un snapshot fourni explicitement est conservé."""
        shift = Shift.objects.create(
            collaborator=self.collab,
            start_datetime=_dt(self.d, 9),
            end_datetime=_dt(self.d, 17),
            contract_hours_snapshot=24.0,
        )
        self.assertEqual(float(shift.contract_hours_snapshot), 24.0)

    def test_snapshot_reflete_heures_au_moment_creation(self):
        """Deux shifts créés avant/après changement de contrat ont des snapshots différents."""
        shift_avant = Shift.objects.create(
            collaborator=self.collab,
            start_datetime=_dt(self.d, 9),
            end_datetime=_dt(self.d, 17),
        )
        self.collab.weekly_hours = 28.0
        self.collab.save(update_fields=['weekly_hours'])
        shift_apres = Shift.objects.create(
            collaborator=self.collab,
            start_datetime=_dt(datetime.date(2026, 3, 10), 9),
            end_datetime=_dt(datetime.date(2026, 3, 10), 17),
        )
        self.assertEqual(float(shift_avant.contract_hours_snapshot), 35.0)
        self.assertEqual(float(shift_apres.contract_hours_snapshot), 28.0)


# ── TimeAdjustment — CheckConstraint duration_minutes > 0 ────────────────────

class TestTimeAdjustmentConstraint(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.d = datetime.date(2026, 3, 9)

    def _make_adj(self, duration_minutes):
        return TimeAdjustment.objects.create(
            collaborator=self.collab,
            date=self.d,
            type=TimeAdjustment.Type.OVERTIME,
            actual_time=datetime.time(17, 0),
            reference_time=datetime.time(16, 0),
            duration_minutes=duration_minutes,
        )

    def test_duration_positive_acceptee(self):
        adj = self._make_adj(60)
        self.assertEqual(adj.duration_minutes, 60)

    def test_duration_zero_viole_contrainte(self):
        with self.assertRaises(IntegrityError):
            self._make_adj(0)

    def test_duration_negative_viole_contrainte(self):
        with self.assertRaises(IntegrityError):
            self._make_adj(-30)

    def test_duration_1_acceptee(self):
        adj = self._make_adj(1)
        self.assertEqual(adj.duration_minutes, 1)
