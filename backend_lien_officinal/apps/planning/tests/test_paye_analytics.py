"""
Tests du récap paie CCN Pharmacie — compute_paye_summary()

Scénario : Marc Dupont, 35h/semaine, mars 2026 (aucun férié ce mois).

Semaines rattachées à mars (règle du vendredi) :
  S10 (2-8  mars)  — vendredi 6  mars
  S11 (9-15 mars)  — vendredi 13 mars
  S12 (16-22 mars) — vendredi 20 mars
  S13 (23-29 mars) — vendredi 27 mars
  S14 (30 mars - 5 avril) — vendredi 3 avril → a_cheval

Shifts : lundi-vendredi 9h-17h (8h/jour, 40h/semaine).
Ajustements :
  - S11 : overtime mardi 10 mars +2h  → total S11 = 42h
  - S13 : early_departure ven 27 mars -1h → total S13 = 39h
Absence injustifiée :
  - S12 : jeudi 19 mars (shift is_absent=True, absence_type='injustifiee') → total S12 = 24h
S14 a_cheval : 2 shifts (lun 30 + mar 31), non comptés dans totaux.

Calculs manuels attendus :
  S10 : total=40h, sup=5h, tr1=5h, tr2=0, dues=0
  S11 : total=42h, sup=7h, tr1=7h, tr2=0, dues=0
  S12 : total=24h, sup=0,  tr1=0,  tr2=0, dues=-8h
  S13 : total=39h, sup=4h, tr1=4h, tr2=0, dues=-1h
  S14 : total=16h, a_cheval → exclu des totaux

  total_sup_tr1    = 5+7+0+4  = 16h
  total_sup_tr2    = 0
  heures_dues      = 0+0-8-1  = -9h
  heures_reelles   = 40+40+32+40 = 152h  (overtime non inclus)
  heures_contrat   = 35 × 4 semaines = 140h
  jours_travailles = 5+5+4+5 = 19 jours
  heures_nuit_20   = 0  (shifts 9h-17h uniquement)
  heures_dimanche  = 0
  jours_feries     = []  (mars 2026 sans férié)
"""

from datetime import date, time
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.core.models import Pharmacy
from apps.team.models import Collaborator
from apps.planning.models import Shift, TimeAdjustment
from apps.planning.paye_analytics import compute_paye_summary

TZ = ZoneInfo("Europe/Paris")

YEAR  = 2026
MONTH = 3   # mars


def dt(d: date, h: int, m: int = 0):
    from datetime import datetime
    return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)


def shift(collab, d: date, h_start=9, h_end=17, absent=False, abs_type=None):
    return Shift(
        collaborator=collab,
        collaborator_snapshot=f"{collab.first_name} {collab.last_name}",
        start_datetime=dt(d, h_start),
        end_datetime=dt(d, h_end),
        is_published=True,
        is_absent=absent,
        absence_type=abs_type,
        contract_hours_snapshot=collab.weekly_hours,
    )


class PayeAnalyticsMarcMars2026(TestCase):

    @classmethod
    def setUpTestData(cls):
        # ── Pharmacie de test ──────────────────────────────────────────────────
        cls.pharmacy = Pharmacy.objects.create(
            email="test_paye@test.com",
            nom_officine="Pharmacie Test Paie",
            onboarding_completed=True,
            is_active=True,
        )
        cls.pharmacy.set_password("test")
        cls.pharmacy.save()

        # ── Collaborateur : Marc Dupont, 35h/semaine, non-TNS ─────────────────
        cls.marc = Collaborator.objects.create(
            pharmacy=cls.pharmacy,
            civility="M.",
            first_name="Marc",
            last_name="Dupont",
            role="Adjoint",
            color="blue",
            weekly_hours=35,
            is_tns=False,
            is_active=True,
        )

        # ── Shifts ─────────────────────────────────────────────────────────────
        # S10 (2-8 mars) : Lun-Ven 9h-17h, tout présent
        s10_days = [date(2026, 3, d) for d in (2, 3, 4, 5, 6)]

        # S11 (9-15 mars) : Lun-Ven 9h-17h, overtime mardi 10/03
        s11_days = [date(2026, 3, d) for d in (9, 10, 11, 12, 13)]

        # S12 (16-22 mars) : Lun-Mer-Ven présents, Jeu 19/03 absent injustifié
        s12_days_present = [date(2026, 3, d) for d in (16, 17, 18, 20)]
        s12_absent = date(2026, 3, 19)

        # S13 (23-29 mars) : Lun-Ven présents, early_departure Ven 27/03
        s13_days = [date(2026, 3, d) for d in (23, 24, 25, 26, 27)]

        # S14 a_cheval (30-31 mars) : 2 shifts
        s14_days = [date(2026, 3, 30), date(2026, 3, 31)]

        shifts_to_create = []
        for d in s10_days + s11_days + s12_days_present + s13_days + s14_days:
            shifts_to_create.append(shift(cls.marc, d))
        shifts_to_create.append(shift(cls.marc, s12_absent, absent=True, abs_type="injustifiee"))

        Shift.objects.bulk_create(shifts_to_create)

        # ── Ajustements horaires ───────────────────────────────────────────────
        # Overtime mardi 10 mars : +2h (9h-17h planifié → 9h-19h réel)
        TimeAdjustment.objects.create(
            collaborator=cls.marc,
            date=date(2026, 3, 10),
            type="overtime",
            actual_time=time(19, 0),
            reference_time=time(17, 0),
            duration_minutes=120,
            note="Inventaire",
        )
        # Early departure vendredi 27 mars : -1h (9h-17h planifié → 9h-16h réel)
        TimeAdjustment.objects.create(
            collaborator=cls.marc,
            date=date(2026, 3, 27),
            type="early_departure",
            actual_time=time(16, 0),
            reference_time=time(17, 0),
            duration_minutes=60,
            note="RDV médical",
        )

    def _get_marc(self, result):
        for c in result["collaborateurs"]:
            if c["nom"] == "Marc Dupont":
                return c
        self.fail("Marc Dupont introuvable dans le résultat")

    def _get_semaine(self, marc_data, week_str_fragment):
        for s in marc_data["detail_semaines"]:
            if week_str_fragment in s["week_str"]:
                return s
        self.fail(f"Semaine contenant '{week_str_fragment}' introuvable")

    # ── Tests ────────────────────────────────────────────────────────────────

    def test_result_contains_marc(self):
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        names = [c["nom"] for c in result["collaborateurs"]]
        self.assertIn("Marc Dupont", names)

    def test_heures_reelles(self):
        """152h = 40+40+32+40 (overtime non inclus, absent exclu)."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        self.assertEqual(marc["heures_reelles"], 152.0)

    def test_heures_contrat(self):
        """140h = 35h × 4 semaines rattachées principales."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        self.assertEqual(marc["heures_contrat"], 140.0)

    def test_jours_travailles(self):
        """19 jours = 5+5+4+5 (jeudi 19 absent, S14 a_cheval hors range)."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        self.assertEqual(marc["jours_travailles"], 19)

    def test_sup_tranche1_total(self):
        """16h = 5+7+0+4 (S14 exclu car a_cheval)."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        self.assertEqual(marc["heures_sup_planning"]["tranche1"], 16.0)

    def test_sup_tranche2_total(self):
        """0h : aucune semaine ne dépasse 43h (35+8)."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        self.assertEqual(marc["heures_sup_planning"]["tranche2"], 0.0)

    def test_heures_dues_total(self):
        """-9h = S12 (-8h abs.inj) + S13 (-1h départ anticipé)."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        self.assertEqual(marc["heures_dues"], -9.0)

    def test_heures_nuit_zero(self):
        """Aucune heure de nuit (shifts 9h-17h uniquement)."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        self.assertEqual(marc["heures_nuit_20"], 0.0)
        self.assertEqual(marc["heures_nuit_40"], 0.0)

    def test_heures_dimanche_zero(self):
        """Aucun shift le dimanche."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        self.assertEqual(marc["heures_dimanche"], 0.0)

    def test_jours_feries_vide(self):
        """Mars 2026 : aucun jour férié."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        self.assertEqual(marc["heures_feries_travaillees"], 0.0)
        self.assertEqual(marc["jours_feries_travailles"], [])

    # ── Détail semaine par semaine ────────────────────────────────────────────

    def test_s10_total_et_sup(self):
        """S10 : 5×8h=40h, sup=5h, tr1=5h."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        s10 = self._get_semaine(marc, "S10")
        self.assertFalse(s10["a_cheval"])
        self.assertEqual(s10["heures_shifts"], 40.0)
        self.assertEqual(s10["heures_overtime"], 0.0)
        self.assertEqual(s10["total_semaine"], 40.0)
        self.assertEqual(s10["sup_tranche1"], 5.0)
        self.assertEqual(s10["sup_tranche2"], 0.0)
        self.assertEqual(s10["heures_dues"], 0.0)

    def test_s11_overtime(self):
        """S11 : 40h shifts + 2h overtime = 42h, tr1=7h."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        s11 = self._get_semaine(marc, "S11")
        self.assertEqual(s11["heures_shifts"], 40.0)
        self.assertEqual(s11["heures_overtime"], 2.0)
        self.assertEqual(s11["total_semaine"], 42.0)
        self.assertEqual(s11["sup_tranche1"], 7.0)
        self.assertEqual(s11["heures_dues"], 0.0)  # overtime compense

    def test_s12_absence_injustifiee(self):
        """S12 : 32h présents - 8h abs.inj = 24h, dues=-8h."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        s12 = self._get_semaine(marc, "S12")
        self.assertEqual(s12["heures_shifts"], 32.0)
        self.assertEqual(s12["heures_absence_injustifiee"], 8.0)
        self.assertEqual(s12["total_semaine"], 24.0)
        self.assertEqual(s12["sup_tranche1"], 0.0)
        self.assertEqual(s12["heures_dues"], -8.0)

    def test_s13_early_departure(self):
        """S13 : 40h shifts - 1h départ ant. = 39h, tr1=4h, dues=-1h."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        s13 = self._get_semaine(marc, "S13")
        self.assertEqual(s13["heures_shifts"], 40.0)
        self.assertEqual(s13["heures_early"], 1.0)
        self.assertEqual(s13["total_semaine"], 39.0)
        self.assertEqual(s13["sup_tranche1"], 4.0)
        self.assertEqual(s13["heures_dues"], -1.0)

    def test_s14_a_cheval(self):
        """S14 (30-31 mars) : a_cheval=True, rattachement=avril."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        s14 = self._get_semaine(marc, "S14")
        self.assertTrue(s14["a_cheval"])
        self.assertEqual(s14["heures_shifts"], 16.0)
        self.assertEqual(s14["total_semaine"], 16.0)
        self.assertEqual(s14["sup_tranche1"], 0.0)  # sous le seuil
        self.assertIn("avril", s14["rattachement"])

    def test_alerte_46h_absente(self):
        """Aucune semaine ne dépasse 46h (max = 42h en S11)."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        alertes = [s["alerte_46h"] for s in marc["detail_semaines"]]
        self.assertFalse(any(alertes))

    def test_absences_ventilees_zero(self):
        """Aucune absence justifiée posée ce mois (injustifiée ne compte pas dans les compteurs)."""
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        self.assertEqual(marc["cp_poses"], 0)
        self.assertEqual(marc["rcr_poses"], 0)
        self.assertEqual(marc["conge_exc_poses"], 0)
        self.assertEqual(marc["sans_solde_poses"], 0)

    def test_rcr_acquis_inclut_adjustments(self):
        """
        rcr_acquis doit inclure les TimeAdjustment (overtime/early) — cohérence
        avec detail_semaines.

        Calcul attendu (données du test, pas de jan/fév) :
          S10 : 40h shifts, 0 adj     → sup = 40-35 = 5h
          S11 : 40h shifts, +2h OT    → sup = 42-35 = 7h
          S12 : 32h shifts (abs_inj non déduit pour rcr annuel) → sup = 0h
          S13 : 40h shifts, -1h early → sup = 39-35 = 4h
          S14 : 16h (a_cheval, <35)   → sup = 0h
          Total = 16h
        """
        result = compute_paye_summary(self.pharmacy, YEAR, MONTH)
        marc = self._get_marc(result)
        annuel = marc["annuel"]
        self.assertEqual(annuel["rcr_acquis"], 16.0)
        # contingent_consomme doit être identique à rcr_acquis
        self.assertEqual(annuel["contingent_consomme"], annuel["rcr_acquis"])
        # Aucun RCR consommé dans ce scénario
        self.assertEqual(annuel["rcr_consomme"], 0.0)
        self.assertEqual(annuel["rcr_solde"], 16.0)
