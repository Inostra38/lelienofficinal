"""
Tests paye_analytics — jours fériés.

Mai 2026 : trois fériés tombant un jour ouvré (Lun-Sam) :
  - 1er mai (vendredi) : Fête du Travail — premier_mai=True
  - 8 mai  (vendredi) : Victoire 1945
  - 21 mai (jeudi)    : Ascension

Vérifications :
  1. jours_ouvres_mois ne compte pas les fériés → < total Lun-Sam du mois
  2. Shift sur 1er mai → jours_feries_travailles contient l'entrée avec premier_mai=True
  3. Shift sur jour non-férié → pas dans jours_feries_travailles
  4. Aucun shift sur un férié → jours_feries_travailles vide, heures_feries_travaillees = 0
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.core.models import Pharmacy
from apps.planning.models import Shift
from apps.planning.paye_analytics import compute_paye_summary
from apps.team.models import Collaborator

TZ = ZoneInfo("Europe/Paris")

YEAR  = 2026
MONTH = 5  # mai


def _make_pharmacy(email):
    p = Pharmacy.objects.create(
        email=email,
        nom_officine="Pharmacie Feries",
        onboarding_completed=True,
        is_active=True,
    )
    p.set_password("test")
    p.save()
    return p


def _make_collab(pharmacy, weekly_hours=35):
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name="Alice",
        last_name="Feries",
        role="Adjoint",
        color="#111111",
        weekly_hours=weekly_hours,
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


class TestPayeAnalyticsFeries(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.pharmacy_normal  = _make_pharmacy("feries_normal@test.com")
        cls.pharmacy_with    = _make_pharmacy("feries_with@test.com")
        cls.pharmacy_without = _make_pharmacy("feries_without@test.com")

        # Pharmacie sans shift sur un férié
        cls.collab_normal = _make_collab(cls.pharmacy_normal)

        # Pharmacie avec shift sur 1er mai
        cls.collab_with = _make_collab(cls.pharmacy_with)

        # Pharmacie sans aucun shift ce mois (vérification propre de _compute_feries)
        cls.collab_without = _make_collab(cls.pharmacy_without)

        # Shifts "normaux" (lundi 4 mai, lundi 11 mai) hors jours fériés
        _shift(cls.collab_normal, date(2026, 5, 4))   # lundi 4 mai
        _shift(cls.collab_normal, date(2026, 5, 11))  # lundi 11 mai

        # Shift sur 1er mai (vendredi, jour férié)
        _shift(cls.collab_with, date(2026, 5, 1))

        # Shifts le 21 mai (jeudi, Ascension) ET un jour normal
        _shift(cls.collab_with, date(2026, 5, 4))

    def test_jours_ouvres_mois_exclut_feries(self):
        """jours_ouvres_mois ne compte pas les 4 fériés tombant un jour ouvré.

        Mai 2026 : 31 jours, 5 dimanches (3,10,17,24,31) → 26 jours Lun-Sam.
        Fériés sur Lun-Sam :
          - 1er mai  (vendredi) : Fête du Travail
          - 8 mai    (vendredi) : Victoire 1945
          - 14 mai   (jeudi)    : Ascension (Pâques 5 avr + 39j)
          - 25 mai   (lundi)    : Lundi de Pentecôte (Pâques + 50j)
        jours_ouvres = 26 - 4 = 22
        """
        result = compute_paye_summary(self.pharmacy_normal, YEAR, MONTH)
        self.assertEqual(result['jours_ouvres_mois'], 22)

    def test_shift_sur_premier_mai_dans_jours_feries_travailles(self):
        """Un shift sur 1er mai → premier_mai=True dans jours_feries_travailles."""
        result = compute_paye_summary(self.pharmacy_with, YEAR, MONTH)
        collab_data = result['collaborateurs'][0]
        jours_feries = collab_data['jours_feries_travailles']
        self.assertEqual(len(jours_feries), 1)
        ferie = jours_feries[0]
        self.assertEqual(ferie['date'], '2026-05-01')
        self.assertTrue(ferie['premier_mai'])
        self.assertGreater(ferie['heures'], 0)

    def test_shift_normal_pas_dans_jours_feries(self):
        """Shift le lundi 4 mai (non-férié) → absent de jours_feries_travailles."""
        result = compute_paye_summary(self.pharmacy_normal, YEAR, MONTH)
        collab_data = result['collaborateurs'][0]
        dates_feries = [j['date'] for j in collab_data['jours_feries_travailles']]
        self.assertNotIn('2026-05-04', dates_feries)

    def test_sans_shift_sur_ferie_zero_heures_feries(self):
        """Aucun shift sur un jour férié → heures_feries_travaillees = 0."""
        result = compute_paye_summary(self.pharmacy_normal, YEAR, MONTH)
        collab_data = result['collaborateurs'][0]
        self.assertEqual(collab_data['heures_feries_travaillees'], 0)
        self.assertEqual(collab_data['jours_feries_travailles'], [])
