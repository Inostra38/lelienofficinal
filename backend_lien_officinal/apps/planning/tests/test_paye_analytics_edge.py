"""
Tests paye_analytics — cas limites (edge cases).

1. Collaborateur temps partiel (24h/sem) — seuil heures sup à 24h
2. Mois sans aucun shift — résultat vide, pas d'exception
3. Heures nuit chevauchant minuit (23h → 01h) — comptage correct plage 22h-05h
4. Deux absences approuvées consécutives sur la même période — pas de doublon
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.core.models import Pharmacy
from apps.planning.models import AbsenceRequest, Shift
from apps.planning.paye_analytics import compute_paye_summary
from apps.team.models import Collaborator

TZ = ZoneInfo("Europe/Paris")

_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    p = Pharmacy.objects.create(
        email=f"edge_{_counter}@test.com",
        nom_officine="Pharmacie Edge",
        onboarding_completed=True,
        is_active=True,
    )
    p.set_password("test")
    p.save()
    return p


def _make_collab(pharmacy, weekly_hours=35, is_tns=False):
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name="Edge",
        last_name="Case",
        role="Adjoint",
        color="#aabbcc",
        weekly_hours=weekly_hours,
        is_tns=is_tns,
        is_active=True,
    )


def _shift(collab, day, h_start=9, h_end=17):
    return Shift.objects.create(
        collaborator=collab,
        start_datetime=datetime(day.year, day.month, day.day, h_start, tzinfo=TZ),
        end_datetime=datetime(day.year, day.month, day.day, h_end, tzinfo=TZ),
        is_published=True,
        contract_hours_snapshot=collab.weekly_hours,
    )


# ── 1. Temps partiel ─────────────────────────────────────────────────────────

class TestTempsPartiel24h(TestCase):
    """
    Collaborateur à 24h/sem.
    3 shifts de 8h = 24h ≤ seuil → heures_sup = 0.
    4 shifts de 8h = 32h > seuil 24h → heures_sup = 8h.
    """

    @classmethod
    def setUpTestData(cls):
        cls.pharmacy = _make_pharmacy()
        cls.collab = _make_collab(cls.pharmacy, weekly_hours=24)

        # S11 (9-15 mars) : 3 shifts (lun-mer-ven 9h-17h)
        # total = 24h = seuil → pas de sup
        for d in [date(2026, 3, 9), date(2026, 3, 11), date(2026, 3, 13)]:
            _shift(cls.collab, d)

        # S10 (2-8 mars) : 4 shifts (lun-mar-mer-jeu 9h-17h)
        # total = 32h > 24h → 8h sup
        for d in [date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 5)]:
            _shift(cls.collab, d)

    def test_seuil_24h_pas_de_sup_a_24h_exactement(self):
        """24h travaillées sur S11 avec seuil 24h → sup_tranche1 = 0."""
        result = compute_paye_summary(self.pharmacy, 2026, 3)
        collab_data = result['collaborateurs'][0]
        # Chercher S11
        s11 = next(s for s in collab_data['detail_semaines'] if '9' in s['week_str'] and 'mars' in s['week_str'])
        self.assertEqual(s11['total_semaine'], 24.0)
        self.assertEqual(s11['sup_tranche1'], 0.0)

    def test_seuil_24h_sup_au_dessus_de_24h(self):
        """32h travaillées sur S10 avec seuil 24h → 8h sup (tranche1)."""
        result = compute_paye_summary(self.pharmacy, 2026, 3)
        collab_data = result['collaborateurs'][0]
        # Chercher S10
        s10 = next(s for s in collab_data['detail_semaines'] if '2' in s['week_str'] and 'mars' in s['week_str'])
        self.assertEqual(s10['total_semaine'], 32.0)
        self.assertEqual(s10['sup_tranche1'], 8.0)


# ── 2. Mois sans shift ───────────────────────────────────────────────────────

class TestMoisSansShift(TestCase):
    """Collaborateur actif sans aucun shift ce mois → résultat vide, pas d'exception."""

    @classmethod
    def setUpTestData(cls):
        cls.pharmacy = _make_pharmacy()
        cls.collab = _make_collab(cls.pharmacy, weekly_hours=35)
        # Aucun shift créé

    def test_resultat_sans_exception(self):
        """compute_paye_summary ne lève pas d'exception sur un mois sans shift."""
        try:
            result = compute_paye_summary(self.pharmacy, 2026, 3)
        except Exception as e:
            self.fail(f"compute_paye_summary a levé une exception : {e}")

    def test_heures_reelles_zero(self):
        """heures_reelles = 0 pour un collaborateur sans shift."""
        result = compute_paye_summary(self.pharmacy, 2026, 3)
        collab_data = result['collaborateurs'][0]
        self.assertEqual(collab_data['heures_reelles'], 0.0)

    def test_jours_travailles_zero(self):
        """jours_travailles = 0 pour un collaborateur sans shift."""
        result = compute_paye_summary(self.pharmacy, 2026, 3)
        collab_data = result['collaborateurs'][0]
        self.assertEqual(collab_data['jours_travailles'], 0)

    def test_sup_zero(self):
        """Aucune heure sup sans shift."""
        result = compute_paye_summary(self.pharmacy, 2026, 3)
        collab_data = result['collaborateurs'][0]
        sup = collab_data['heures_sup_planning']
        self.assertEqual(sup['total'], 0.0)
        self.assertEqual(sup['tranche1'], 0.0)
        self.assertEqual(sup['tranche2'], 0.0)


# ── 3. Heures nuit chevauchant minuit ─────────────────────────────────────────

class TestHeuresNuitChevauchantMinuit(TestCase):
    """
    Shift de 23h à 01h (cross-midnight) :
    - plage nuit 40% : 22h-05h → le shift est entièrement dans cette plage → 2h
    - plage nuit 20% : 20h-22h et 05h-08h → non chevauchées → 0h
    """

    @classmethod
    def setUpTestData(cls):
        cls.pharmacy = _make_pharmacy()
        cls.collab = _make_collab(cls.pharmacy, weekly_hours=35)

        # Shift lundi 2 mars 23h → mardi 3 mars 01h
        d_start = date(2026, 3, 2)
        d_end   = date(2026, 3, 3)
        Shift.objects.create(
            collaborator=cls.collab,
            start_datetime=datetime(d_start.year, d_start.month, d_start.day, 23, 0, tzinfo=TZ),
            end_datetime=datetime(d_end.year, d_end.month, d_end.day, 1, 0, tzinfo=TZ),
            is_published=True,
            contract_hours_snapshot=35,
        )

    def test_heures_nuit_40_correctes(self):
        """2h entre 23h et 01h → entièrement dans plage 22h-05h → heures_nuit_40 = 2."""
        result = compute_paye_summary(self.pharmacy, 2026, 3)
        collab_data = result['collaborateurs'][0]
        self.assertEqual(collab_data['heures_nuit_40'], 2.0)

    def test_heures_nuit_20_zero(self):
        """Shift 23h-01h ne touche pas les plages 20h-22h ni 05h-08h → heures_nuit_20 = 0."""
        result = compute_paye_summary(self.pharmacy, 2026, 3)
        collab_data = result['collaborateurs'][0]
        self.assertEqual(collab_data['heures_nuit_20'], 0.0)


# ── 4. Deux absences consécutives ─────────────────────────────────────────────

class TestDeuxAbsencesConsecutives(TestCase):
    """
    Deux absences CP approuvées qui ne se chevauchent pas :
    une du 9 au 13 mars, une du 16 au 20 mars.
    cp_poses doit être 10 (5 + 5), pas de doublon.
    """

    @classmethod
    def setUpTestData(cls):
        cls.pharmacy = _make_pharmacy()
        cls.collab = _make_collab(cls.pharmacy, weekly_hours=35)

        AbsenceRequest.objects.create(
            collaborator=cls.collab,
            start_date=date(2026, 3, 9),
            end_date=date(2026, 3, 13),
            type='cp',
            status='approved',
        )
        AbsenceRequest.objects.create(
            collaborator=cls.collab,
            start_date=date(2026, 3, 16),
            end_date=date(2026, 3, 20),
            type='cp',
            status='approved',
        )

    def test_deux_absences_cp_pas_de_doublon(self):
        """cp_poses = 10 jours ouvrés (2 semaines × 5j), pas de doublon."""
        result = compute_paye_summary(self.pharmacy, 2026, 3)
        collab_data = result['collaborateurs'][0]
        # 9-13 mars : lun-ven = 5j ouvrés (pas de férié cette semaine)
        # 16-20 mars : lun-ven = 5j ouvrés
        self.assertEqual(collab_data['cp_poses'], 10)
