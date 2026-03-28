"""
Tests du récap paie CCN Pharmacie — octobre 2026

Calendrier octobre 2026 (aucun jour férié, pas de semaine à cheval) :
  S40  (lun 28 sep – dim  4 oct)  vendredi  2 oct  → octobre   rattaché=false
  S41  (lun  5 oct – dim 11 oct)  vendredi  9 oct  → octobre
  S42  (lun 12 oct – dim 18 oct)  vendredi 16 oct  → octobre
  S43  (lun 19 oct – dim 25 oct)  vendredi 23 oct  → octobre
  S44  (lun 26 oct – dim  1 nov)  vendredi 30 oct  → octobre
  ⇒ 5 semaines principales, heures_contrat = 35 × 5 = 175 h

Scénario — Sophie Lange, 35h/semaine, non-TNS :

  S40 (28 sep–4 oct)  : Lun-Ven 9h-17h (5×8h=40h) + Dim 4 oct 10h-14h (4h)
    → heures_shifts=44h, total=44h, sup=9h, tr1=8h, tr2=1h
    → heures_dimanche += 4h

  S41 (5–11 oct)      : shifts nuit Lun-Ven 20h-04h (8h chacun = 40h)
    → heures_shifts=40h, total=40h, sup=5h, tr1=5h, tr2=0h
    → nuit_20 += 2h/shift × 5 = 10h  (plage 20h-22h)
    → nuit_40 += 6h/shift × 5 = 30h  (plage 22h-04h)

  S42 (12–18 oct)     : CP toute la semaine (AbsenceRequest 12-16 oct)
    → heures_shifts=0, total=0h, sup=0h, cp_poses=5j

  S43 (19–25 oct)     : Lun-Ven 9h-17h (40h) + Sam 24 oct 9h-13h (4h)
    → heures_shifts=44h, total=44h, sup=9h, tr1=8h, tr2=1h

  S44 (26 oct–1 nov)  : Lun-Ven 9h-17h (40h)
    → heures_shifts=40h, total=40h, sup=5h, tr1=5h, tr2=0h

Totaux globaux attendus :
  heures_reelles   = 40+4+40+0+44+40 = 168 h  (absences CP non comptées)
  heures_contrat   = 35 × 5 = 175 h
  jours_travailles = 6+5+0+6+5 = 22 j
  sup_tr1          = 8+5+0+8+5 = 26 h
  sup_tr2          = 1+0+0+1+0 = 2 h
  heures_dues      = 0  (aucune absence injustifiée ni départ anticipé)
  heures_nuit_20   = 10 h
  heures_nuit_40   = 30 h
  heures_dimanche  = 4 h
  cp_poses         = 5 j
  jours_feries     = []  (octobre sans férié)
"""

from datetime import date, time, datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.core.models import Pharmacy
from apps.team.models import Collaborator
from apps.planning.models import AbsenceRequest, Shift
from apps.planning.paye_analytics import compute_paye_summary

TZ = ZoneInfo("Europe/Paris")

YEAR  = 2026
MONTH = 10   # octobre


def dt(d: date, h: int, m: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)


def make_shift(collab, d: date, h_start: int, h_end: int,
               end_date: date | None = None,
               absent=False, abs_type=None) -> Shift:
    """Crée un Shift (non persisté) avec end_date optionnel pour les cross-midnight."""
    end_d = end_date or d
    return Shift(
        collaborator=collab,
        collaborator_snapshot=f"{collab.first_name} {collab.last_name}",
        start_datetime=dt(d, h_start),
        end_datetime=dt(end_d, h_end),
        is_published=True,
        is_absent=absent,
        absence_type=abs_type,
        contract_hours_snapshot=collab.weekly_hours,
    )


class PayeAnalyticsSophieOctobre2026(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.pharmacy = Pharmacy.objects.create(
            email="test_paye_oct@test.com",
            nom_officine="Pharmacie Test Octobre",
            onboarding_completed=True,
            is_active=True,
        )
        cls.pharmacy.set_password("test")
        cls.pharmacy.save()

        cls.sophie = Collaborator.objects.create(
            pharmacy=cls.pharmacy,
            civility="Mme",
            first_name="Sophie",
            last_name="Lange",
            role="Préparatrice",
            color="#22c55e",
            weekly_hours=35,
            is_tns=False,
            is_active=True,
        )

        shifts_to_create = []

        # ── S40 : Lun-Ven 9h-17h + Dimanche 4 oct 10h-14h ──────────────────
        for day in (28, 29, 30):  # sep
            shifts_to_create.append(
                make_shift(cls.sophie, date(2026, 9, day), 9, 17))
        for day in (1, 2):        # oct (jeu + ven)
            shifts_to_create.append(
                make_shift(cls.sophie, date(2026, 10, day), 9, 17))
        # Dimanche 4 oct
        shifts_to_create.append(
            make_shift(cls.sophie, date(2026, 10, 4), 10, 14))

        # ── S41 : nuit 20h-04h Lun-Ven ──────────────────────────────────────
        for day in (5, 6, 7, 8, 9):   # oct
            shifts_to_create.append(
                make_shift(cls.sophie,
                           date(2026, 10, day), 20, 4,
                           end_date=date(2026, 10, day + 1)))

        # ── S42 : aucun shift (CP via AbsenceRequest) ────────────────────────
        # (créé séparément ci-dessous)

        # ── S43 : Lun-Ven 9h-17h + Sam 24 oct 9h-13h ───────────────────────
        for day in (19, 20, 21, 22, 23):
            shifts_to_create.append(
                make_shift(cls.sophie, date(2026, 10, day), 9, 17))
        shifts_to_create.append(
            make_shift(cls.sophie, date(2026, 10, 24), 9, 13))

        # ── S44 : Lun-Ven 9h-17h ────────────────────────────────────────────
        for day in (26, 27, 28, 29, 30):
            shifts_to_create.append(
                make_shift(cls.sophie, date(2026, 10, day), 9, 17))

        Shift.objects.bulk_create(shifts_to_create)

        # CP semaine S42 : Lun-Ven 12-16 oct
        AbsenceRequest.objects.create(
            collaborator=cls.sophie,
            type='cp',
            status='approved',
            start_date=date(2026, 10, 12),
            end_date=date(2026, 10, 16),
            working_days_count=5,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _result(self):
        return compute_paye_summary(self.pharmacy, YEAR, MONTH)

    def _get_sophie(self, result):
        for c in result["collaborateurs"]:
            if c["nom"] == "Sophie Lange":
                return c
        self.fail("Sophie Lange introuvable dans le résultat")

    def _get_semaine(self, sophie_data, week_fragment):
        for s in sophie_data["detail_semaines"]:
            if week_fragment in s["week_str"]:
                return s
        self.fail(f"Semaine '{week_fragment}' introuvable")

    # ── Structure ─────────────────────────────────────────────────────────────

    def test_result_contains_sophie(self):
        result = self._result()
        names = [c["nom"] for c in result["collaborateurs"]]
        self.assertIn("Sophie Lange", names)

    def test_cinq_semaines_octobre(self):
        """Octobre 2026 : 5 semaines rattachées, aucune à cheval."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(len(sophie["detail_semaines"]), 5)
        self.assertFalse(any(s["a_cheval"] for s in sophie["detail_semaines"]))

    # ── Totaux globaux ────────────────────────────────────────────────────────

    def test_heures_reelles(self):
        """168h = S40(44) + S41(40) + S42(0) + S43(44) + S44(40)."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["heures_reelles"], 168.0)

    def test_heures_contrat(self):
        """175h = 35h × 5 semaines."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["heures_contrat"], 175.0)

    def test_jours_travailles(self):
        """22j = S40(6) + S41(5) + S42(0) + S43(6) + S44(5)."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["jours_travailles"], 22)

    def test_sup_tranche1(self):
        """26h = S40(8) + S41(5) + S42(0) + S43(8) + S44(5)."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["heures_sup_planning"]["tranche1"], 26.0)

    def test_sup_tranche2(self):
        """2h = S40(1) + S43(1)  (semaines à 44h dépassent 43h)."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["heures_sup_planning"]["tranche2"], 2.0)

    def test_heures_dues_zero(self):
        """Aucune absence injustifiée ni départ anticipé."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["heures_dues"], 0.0)

    # ── Nuit ─────────────────────────────────────────────────────────────────

    def test_heures_nuit_20(self):
        """10h = 5 shifts × 2h (plage 20h-22h)."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["heures_nuit_20"], 10.0)

    def test_heures_nuit_40(self):
        """30h = 5 shifts × 6h (plage 22h-04h)."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["heures_nuit_40"], 30.0)

    # ── Dimanche ─────────────────────────────────────────────────────────────

    def test_heures_dimanche(self):
        """4h : shift dimanche 4 oct 10h-14h."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["heures_dimanche"], 4.0)

    # ── CP ───────────────────────────────────────────────────────────────────

    def test_cp_poses(self):
        """5 jours CP (lun 12 – ven 16 oct)."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["cp_poses"], 5)

    def test_autres_absences_zero(self):
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["rcr_poses"], 0)
        self.assertEqual(sophie["conge_exc_poses"], 0)
        self.assertEqual(sophie["sans_solde_poses"], 0)

    # ── Jours fériés ─────────────────────────────────────────────────────────

    def test_pas_de_feries_octobre(self):
        """Octobre 2026 : aucun jour férié."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertEqual(sophie["heures_feries_travaillees"], 0.0)
        self.assertEqual(sophie["jours_feries_travailles"], [])

    # ── Détail semaines ───────────────────────────────────────────────────────

    def test_s40_dimanche_inclus(self):
        """S40 : 5×8h + 4h dim = 44h, tr1=8h, tr2=1h."""
        result = self._result()
        sophie = self._get_sophie(result)
        s40 = self._get_semaine(sophie, "S40")
        self.assertEqual(s40["heures_shifts"], 44.0)
        self.assertEqual(s40["total_semaine"], 44.0)
        self.assertEqual(s40["sup_tranche1"], 8.0)
        self.assertEqual(s40["sup_tranche2"], 1.0)
        self.assertFalse(s40["a_cheval"])

    def test_s41_nuit(self):
        """S41 : 5×8h nuit = 40h, tr1=5h, tr2=0."""
        result = self._result()
        sophie = self._get_sophie(result)
        s41 = self._get_semaine(sophie, "S41")
        self.assertEqual(s41["heures_shifts"], 40.0)
        self.assertEqual(s41["total_semaine"], 40.0)
        self.assertEqual(s41["sup_tranche1"], 5.0)
        self.assertEqual(s41["sup_tranche2"], 0.0)

    def test_s42_cp(self):
        """S42 : CP → 0h de shifts, pas de sup."""
        result = self._result()
        sophie = self._get_sophie(result)
        s42 = self._get_semaine(sophie, "S42")
        self.assertEqual(s42["heures_shifts"], 0.0)
        self.assertEqual(s42["total_semaine"], 0.0)
        self.assertEqual(s42["sup_tranche1"], 0.0)
        self.assertEqual(s42["heures_dues"], 0.0)   # CP = absence justifiée

    def test_s43_samedi(self):
        """S43 : 5×8h + 4h sam = 44h, tr1=8h, tr2=1h."""
        result = self._result()
        sophie = self._get_sophie(result)
        s43 = self._get_semaine(sophie, "S43")
        self.assertEqual(s43["heures_shifts"], 44.0)
        self.assertEqual(s43["total_semaine"], 44.0)
        self.assertEqual(s43["sup_tranche1"], 8.0)
        self.assertEqual(s43["sup_tranche2"], 1.0)

    def test_s44_normal(self):
        """S44 : 5×8h = 40h, tr1=5h, tr2=0."""
        result = self._result()
        sophie = self._get_sophie(result)
        s44 = self._get_semaine(sophie, "S44")
        self.assertEqual(s44["heures_shifts"], 40.0)
        self.assertEqual(s44["total_semaine"], 40.0)
        self.assertEqual(s44["sup_tranche1"], 5.0)
        self.assertEqual(s44["sup_tranche2"], 0.0)

    def test_alerte_46h_absente(self):
        """Aucune semaine ne dépasse 46h (max = 44h)."""
        result = self._result()
        sophie = self._get_sophie(result)
        self.assertFalse(any(s["alerte_46h"] for s in sophie["detail_semaines"]))
