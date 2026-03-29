"""
Tests paye_analytics — collaborateur TNS (Travailleur Non Salarié).

Pour un TNS :
  - heures_reelles calculées normalement
  - heures_contrat, heures_sup_planning, detail_semaines = None (pas de suivi heures sup)
  - absence_counts (cp_poses, rcr_poses...) = None
  - is_tns = True dans la réponse
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.core.models import Pharmacy
from apps.planning.models import Shift
from apps.planning.paye_analytics import compute_paye_summary
from apps.team.models import Collaborator

TZ = ZoneInfo("Europe/Paris")


def _make_pharmacy():
    p = Pharmacy.objects.create(
        email="tns_test@test.com",
        nom_officine="Pharmacie TNS",
        onboarding_completed=True,
        is_active=True,
    )
    p.set_password("test")
    p.save()
    return p


def _shift(collab, day, h_start=9, h_end=17):
    return Shift.objects.create(
        collaborator=collab,
        start_datetime=datetime(day.year, day.month, day.day, h_start, tzinfo=TZ),
        end_datetime=datetime(day.year, day.month, day.day, h_end, tzinfo=TZ),
        is_published=True,
        contract_hours_snapshot=collab.weekly_hours,
    )


class TestPayeAnalyticsTNS(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.pharmacy = _make_pharmacy()

        # TNS : pas de calcul heures sup
        cls.collab = Collaborator.objects.create(
            pharmacy=cls.pharmacy,
            first_name="Sophie",
            last_name="Titulaire",
            role="Titulaire",
            color="#aaaaaa",
            weekly_hours=35,
            is_tns=True,
            is_active=True,
        )

        # 3 shifts (lun-mer-ven) en mars 2026
        for d in [date(2026, 3, 2), date(2026, 3, 4), date(2026, 3, 6)]:
            _shift(cls.collab, d)

    def _get_collab_data(self):
        result = compute_paye_summary(self.pharmacy, 2026, 3)
        self.assertEqual(len(result['collaborateurs']), 1)
        return result['collaborateurs'][0]

    def test_is_tns_true(self):
        """is_tns=True présent dans les données du collaborateur."""
        data = self._get_collab_data()
        self.assertTrue(data['is_tns'])

    def test_heures_reelles_calculees(self):
        """heures_reelles est calculé normalement (3 shifts × 8h = 24h)."""
        data = self._get_collab_data()
        self.assertEqual(data['heures_reelles'], 24.0)

    def test_heures_contrat_none(self):
        """heures_contrat = None pour un TNS (pas de seuil heures sup)."""
        data = self._get_collab_data()
        self.assertIsNone(data['heures_contrat'])

    def test_heures_sup_none(self):
        """heures_sup_planning = None pour un TNS."""
        data = self._get_collab_data()
        self.assertIsNone(data['heures_sup_planning'])

    def test_detail_semaines_none(self):
        """detail_semaines = None pour un TNS (pas de détail semaine par semaine)."""
        data = self._get_collab_data()
        self.assertIsNone(data['detail_semaines'])

    def test_absences_none(self):
        """cp_poses, rcr_poses, conge_exc_poses, sans_solde_poses = None pour un TNS."""
        data = self._get_collab_data()
        self.assertIsNone(data['cp_poses'])
        self.assertIsNone(data['rcr_poses'])
        self.assertIsNone(data['conge_exc_poses'])
        self.assertIsNone(data['sans_solde_poses'])
