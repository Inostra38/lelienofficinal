"""
Tests de calculator.py — week_summary(), _week_summary_from_data()
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.core.models import Pharmacy
from apps.planning.calculator import week_summary
from apps.planning.models import AbsenceRequest, Shift, TimeAdjustment
from apps.team.models import Collaborator

TZ = ZoneInfo("Europe/Paris")

# Semaine de référence : lundi 9 mars 2026 → dimanche 15 mars 2026
MONDAY = date(2026, 3, 9)

_pharmacy_counter = 0


def _dt(d: date, h: int, m: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)


def _make_pharmacy() -> Pharmacy:
    global _pharmacy_counter
    _pharmacy_counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_calc_{_pharmacy_counter}@test.com",
        password="pass",
        nom_officine="Pharmacie Test",
    )


def _make_collab(pharmacy: Pharmacy, weekly_hours: float = 35.0,
                 first_name: str = "Test", last_name: str = "Collab") -> Collaborator:
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name=first_name,
        last_name=last_name,
        role=Collaborator.Role.PREPARATEUR,
        color="#1a2b3c",
        weekly_hours=weekly_hours,
    )


def _make_shift(collab: Collaborator, d: date, h_start: int = 9, h_end: int = 17,
                published: bool = True) -> Shift:
    return Shift.objects.create(
        collaborator=collab,
        start_datetime=_dt(d, h_start),
        end_datetime=_dt(d, h_end),
        is_published=published,
    )


def _shifts_n_days(collab: Collaborator, n: int, h_start: int, h_end: int):
    """Crée n shifts consécutifs à partir de lundi."""
    for i in range(n):
        _make_shift(collab, date(2026, 3, 9 + i), h_start=h_start, h_end=h_end)


# ── Collaborateur sans aucun shift ────────────────────────────────────────────

class TestWeekSummaryNoShifts(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, weekly_hours=35.0)

    def test_planned_h_zero(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['planned_h'], 0.0)

    def test_extra_h_zero(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['extra_h'], 0.0)

    def test_balance_negatif(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['balance_h'], -35.0)

    def test_shifts_liste_vide(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['shifts'], [])

    def test_days_7_entrees(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(len(result['days']), 7)

    def test_contract_hours_from_model(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['contract_hours'], 35.0)


# ── Collaborateur avec 1 shift de 8h ─────────────────────────────────────────

class TestWeekSummaryOneShift(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, weekly_hours=35.0)
        self.shift = _make_shift(self.collab, MONDAY, h_start=9, h_end=17)

    def test_planned_h_huit(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['planned_h'], 8.0)

    def test_un_shift_dans_liste(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(len(result['shifts']), 1)

    def test_shift_date_correcte(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['shifts'][0]['date'], MONDAY.isoformat())

    def test_balance_sous_seuil(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['balance_h'], 8.0 - 35.0)

    def test_pas_dheures_sup(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['extra_h'], 0.0)


# ── Absence approuvée ─────────────────────────────────────────────────────────

class TestWeekSummaryWithApprovedAbsence(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, weekly_hours=35.0)
        _make_shift(self.collab, MONDAY, h_start=9, h_end=17)
        self.absence = AbsenceRequest.objects.create(
            collaborator=self.collab,
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 11),
            type=AbsenceRequest.AbsenceType.CP,
            status=AbsenceRequest.Status.APPROVED,
            start_period='morning',
            end_period='evening',
        )

    def test_absence_dans_resultats(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(len(result['absences']), 1)

    def test_absence_type_cp(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['absences'][0]['type'], AbsenceRequest.AbsenceType.CP)

    def test_absence_type_dans_days(self):
        result = week_summary(self.collab, MONDAY)
        mardi = next(d for d in result['days'] if d['date'] == '2026-03-10')
        self.assertEqual(mardi['absence_type'], AbsenceRequest.AbsenceType.CP)

    def test_lundi_sans_absence(self):
        result = week_summary(self.collab, MONDAY)
        lundi = next(d for d in result['days'] if d['date'] == '2026-03-09')
        self.assertIsNone(lundi['absence_type'])

    def test_absence_pending_non_comptee(self):
        self.absence.status = AbsenceRequest.Status.PENDING
        self.absence.save()
        result = week_summary(self.collab, MONDAY)
        mardi = next(d for d in result['days'] if d['date'] == '2026-03-10')
        self.assertIsNone(mardi['absence_type'])


# ── Calcul heures supplémentaires 25%/50% ────────────────────────────────────

class TestHeuresSupplementaires(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, weekly_hours=35.0)

    def test_40h_cinq_heures_sup_tr1(self):
        """40h avec contrat 35h → 5h sup, toutes TR1 (≤8h)."""
        _shifts_n_days(self.collab, 5, h_start=9, h_end=17)  # 5×8h=40h
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['planned_h'], 40.0)
        self.assertEqual(result['extra_h'], 5.0)
        self.assertEqual(result['extra_h_25'], 5.0)
        self.assertEqual(result['extra_h_50'], 0.0)

    def test_43h_huit_tr1_zero_tr2(self):
        """43h avec contrat 35h → 8h sup, 8h TR1, 0 TR2 (seuil exact)."""
        _shifts_n_days(self.collab, 5, h_start=8, h_end=17)   # 5×9h=45h... dépasse
        # On veut 43h : 5×8h=40 + ajustement. Plus simple : 4j×9h + 1j×7h = 43h
        Shift.objects.filter(collaborator=self.collab).delete()
        for i in range(4):
            _make_shift(self.collab, date(2026, 3, 9 + i), h_start=8, h_end=17)
        _make_shift(self.collab, date(2026, 3, 13), h_start=9, h_end=16)
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['planned_h'], 43.0)
        self.assertEqual(result['extra_h'], 8.0)
        self.assertEqual(result['extra_h_25'], 8.0)
        self.assertEqual(result['extra_h_50'], 0.0)

    def test_45h_huit_tr1_deux_tr2(self):
        """45h avec contrat 35h → 10h sup : 8h TR1, 2h TR2."""
        _shifts_n_days(self.collab, 5, h_start=8, h_end=17)   # 5×9h=45h
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['planned_h'], 45.0)
        self.assertEqual(result['extra_h'], 10.0)
        self.assertEqual(result['extra_h_25'], 8.0)
        self.assertEqual(result['extra_h_50'], 2.0)

    def test_30h_pas_dheures_sup_balance_neg(self):
        """30h avec contrat 35h → 0 sup, balance -5h."""
        _shifts_n_days(self.collab, 5, h_start=9, h_end=15)   # 5×6h=30h
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['planned_h'], 30.0)
        self.assertEqual(result['extra_h'], 0.0)
        self.assertEqual(result['balance_h'], -5.0)

    def test_extra_h_jamais_negatif(self):
        """extra_h ne peut jamais être négatif."""
        result = week_summary(self.collab, MONDAY)
        self.assertGreaterEqual(result['extra_h'], 0.0)

    def test_contrat_24h_seuil_correct(self):
        """Temps partiel 24h/sem — heures sup dès 24h01, pas dès 35h."""
        collab_24 = _make_collab(self.pharmacy, weekly_hours=24.0,
                                 first_name="Partiel", last_name="Temps")
        _shifts_n_days(collab_24, 4, h_start=9, h_end=16)    # 4×7h=28h
        result = week_summary(collab_24, MONDAY)
        self.assertEqual(result['planned_h'], 28.0)
        self.assertEqual(result['extra_h'], 4.0)
        self.assertEqual(result['extra_h_25'], 4.0)


# ── Ajustements horaires ──────────────────────────────────────────────────────

class TestAjustementsHoraires(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, weekly_hours=35.0)
        _shifts_n_days(self.collab, 5, h_start=9, h_end=16)   # 5×7h=35h

    def test_overtime_ajoute_heures(self):
        TimeAdjustment.objects.create(
            collaborator=self.collab,
            date=MONDAY,
            type=TimeAdjustment.Type.OVERTIME,
            actual_time=time(17, 0),
            reference_time=time(16, 0),
            duration_minutes=60,
        )
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['planned_h'], 36.0)

    def test_early_departure_retire_heures(self):
        TimeAdjustment.objects.create(
            collaborator=self.collab,
            date=MONDAY,
            type=TimeAdjustment.Type.EARLY_DEPARTURE,
            actual_time=time(15, 0),
            reference_time=time(16, 0),
            duration_minutes=60,
        )
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['planned_h'], 34.0)


# ── Métadonnées du résumé ─────────────────────────────────────────────────────

class TestWeekSummaryMetadata(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, weekly_hours=28.0,
                                   first_name="Alice", last_name="Martin")

    def test_full_name(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['full_name'], "Alice Martin")

    def test_collaborator_id(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['collaborator_id'], self.collab.id)

    def test_contract_hours(self):
        result = week_summary(self.collab, MONDAY)
        self.assertEqual(result['contract_hours'], 28.0)

    def test_week_start_milieu_semaine(self):
        """week_summary normalise n'importe quel jour vers le lundi de sa semaine."""
        result_from_wednesday = week_summary(self.collab, date(2026, 3, 11))
        result_from_monday = week_summary(self.collab, MONDAY)
        self.assertEqual(result_from_wednesday['days'], result_from_monday['days'])


# ── Semaine avec jour férié ET absence ────────────────────────────────────────

class TestWeekSummaryHolidayAbsence(TestCase):
    """
    Semaine du lundi 27 avril 2026, qui contient le vendredi 1er mai (férié).
    Shift sur le 1er mai + absence CP sur le même jour.
    → absence_type = 'cp' sur ce jour, worked_h = 8h (le calculator ne déduit pas les fériés).
    """

    MONDAY_WEEK = date(2026, 4, 27)   # Lun 27 avril
    MAI_1 = date(2026, 5, 1)          # Ven 1er mai (férié)

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, weekly_hours=35.0)
        # Shift 9h-17h sur le 1er mai
        _make_shift(self.collab, self.MAI_1, h_start=9, h_end=17)
        # Absence CP sur le 1er mai (journée entière)
        AbsenceRequest.objects.create(
            collaborator=self.collab,
            start_date=self.MAI_1,
            end_date=self.MAI_1,
            type=AbsenceRequest.AbsenceType.CP,
            status=AbsenceRequest.Status.APPROVED,
            start_period='morning',
            end_period='evening',
        )

    def _day_mai_1(self):
        result = week_summary(self.collab, self.MONDAY_WEEK)
        return next(d for d in result['days'] if d['date'] == '2026-05-01')

    def test_absence_type_cp_sur_ferie(self):
        """Le 1er mai avec absence CP → absence_type = 'cp'."""
        self.assertEqual(self._day_mai_1()['absence_type'], AbsenceRequest.AbsenceType.CP)

    def test_worked_h_shift_compte_malgre_ferie(self):
        """Le shift du 1er mai est compté (calculator sans logique jours fériés) → worked_h = 8."""
        self.assertEqual(self._day_mai_1()['worked_h'], 8.0)

    def test_absence_dans_liste_absences(self):
        """L'absence CP du 1er mai apparaît dans result['absences']."""
        result = week_summary(self.collab, self.MONDAY_WEEK)
        self.assertEqual(len(result['absences']), 1)
        self.assertEqual(result['absences'][0]['type'], AbsenceRequest.AbsenceType.CP)
