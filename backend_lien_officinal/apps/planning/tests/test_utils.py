"""
Tests de utils.py — get_jours_feries(), compute_cp_days(), parse_ai_planning_response()
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.planning.utils import (
    AIParseError,
    compute_cp_days,
    get_jours_feries,
    parse_ai_planning_response,
)


# ── get_jours_feries ───────────────────────────────────────────────────────────

class TestGetJoursFeries(TestCase):

    def _paques(self, year: int) -> date:
        """Récupère la date de Pâques (dimanche) pour l'année donnée."""
        feries = get_jours_feries(year)
        lundi_paques = feries[1]  # index 1 = lundi de Pâques
        return lundi_paques - __import__('datetime').timedelta(days=1)

    def test_nombre_feries(self):
        """11 jours fériés pour chaque année."""
        for year in [2024, 2025, 2026, 2027, 2028]:
            with self.subTest(year=year):
                self.assertEqual(len(get_jours_feries(year)), 11)

    def test_1er_mai_toujours_present(self):
        for year in [2024, 2025, 2026, 2027]:
            with self.subTest(year=year):
                self.assertIn(date(year, 5, 1), get_jours_feries(year))

    def test_11_novembre_toujours_present(self):
        for year in [2024, 2025, 2026, 2027]:
            with self.subTest(year=year):
                self.assertIn(date(year, 11, 11), get_jours_feries(year))

    def test_paques_2025(self):
        # Pâques 2025 = 20 avril (algorithme validé)
        self.assertEqual(self._paques(2025), date(2025, 4, 20))
        self.assertIn(date(2025, 4, 21), get_jours_feries(2025))  # lundi de Pâques

    def test_paques_2026(self):
        # Pâques 2026 = 5 avril
        self.assertEqual(self._paques(2026), date(2026, 4, 5))
        self.assertIn(date(2026, 4, 6), get_jours_feries(2026))

    def test_paques_2027(self):
        # Pâques 2027 = 28 mars
        self.assertEqual(self._paques(2027), date(2027, 3, 28))
        self.assertIn(date(2027, 3, 29), get_jours_feries(2027))

    def test_paques_2028(self):
        # Pâques 2028 = 16 avril
        self.assertEqual(self._paques(2028), date(2028, 4, 16))
        self.assertIn(date(2028, 4, 17), get_jours_feries(2028))

    def test_paques_2024(self):
        # Pâques 2024 = 31 mars
        self.assertEqual(self._paques(2024), date(2024, 3, 31))
        self.assertIn(date(2024, 4, 1), get_jours_feries(2024))

    def test_feries_fixes_2026(self):
        feries = set(get_jours_feries(2026))
        expected_fixes = [
            date(2026, 1, 1),   # Jour de l'An
            date(2026, 5, 1),   # Fête du Travail
            date(2026, 5, 8),   # Victoire 1945
            date(2026, 7, 14),  # Fête Nationale
            date(2026, 8, 15),  # Assomption
            date(2026, 11, 1),  # Toussaint
            date(2026, 11, 11), # Armistice
            date(2026, 12, 25), # Noël
        ]
        for d in expected_fixes:
            with self.subTest(date=d):
                self.assertIn(d, feries)

    def test_pas_de_doublons(self):
        for year in [2024, 2025, 2026]:
            with self.subTest(year=year):
                feries = get_jours_feries(year)
                self.assertEqual(len(feries), len(set(feries)))


# ── compute_cp_days ────────────────────────────────────────────────────────────

class TestComputeCpDays(TestCase):
    """
    Teste les 4 combinaisons period (matin/après-midi × matin/soir).
    Semaine de référence : lundi 6 janvier au vendredi 10 janvier 2025 (pas de férié).
    """

    def test_morning_to_evening_full_week(self):
        # 5 jours ouvrés lun-ven, journées complètes → 5,0 j
        result = compute_cp_days(
            date(2025, 1, 6), date(2025, 1, 10),
            start_period='morning', end_period='evening',
        )
        self.assertEqual(result, Decimal('5.0'))

    def test_morning_to_morning_minus_half_end(self):
        # morning → morning = -0,5j fin → 4,5j
        result = compute_cp_days(
            date(2025, 1, 6), date(2025, 1, 10),
            start_period='morning', end_period='morning',
        )
        self.assertEqual(result, Decimal('4.5'))

    def test_afternoon_to_evening_minus_half_start(self):
        # afternoon → evening = -0,5j début → 4,5j
        result = compute_cp_days(
            date(2025, 1, 6), date(2025, 1, 10),
            start_period='afternoon', end_period='evening',
        )
        self.assertEqual(result, Decimal('4.5'))

    def test_afternoon_to_morning_minus_one(self):
        # afternoon → morning = -0,5j début -0,5j fin → 4,0j
        result = compute_cp_days(
            date(2025, 1, 6), date(2025, 1, 10),
            start_period='afternoon', end_period='morning',
        )
        self.assertEqual(result, Decimal('4.0'))

    def test_semaine_avec_ferie_1er_mai(self):
        # Semaine du lun 28 avr au ven 2 mai 2025 — jeudi 1er mai est férié
        # Lun + Mar + Mer + Ven = 4 jours ouvrés (jeudi 1er mai exclu)
        result = compute_cp_days(
            date(2025, 4, 28), date(2025, 5, 2),
            start_period='morning', end_period='evening',
        )
        self.assertEqual(result, Decimal('4.0'))

    def test_dimanche_exclu(self):
        # Lun 6 → dim 12 janvier 2025 : 6 jours (lun-sam), pas dimanche
        result = compute_cp_days(
            date(2025, 1, 6), date(2025, 1, 12),
            start_period='morning', end_period='evening',
        )
        self.assertEqual(result, Decimal('6.0'))

    def test_un_seul_jour_morning_evening(self):
        result = compute_cp_days(
            date(2025, 1, 6), date(2025, 1, 6),
            start_period='morning', end_period='evening',
        )
        self.assertEqual(result, Decimal('1.0'))

    def test_un_seul_jour_afternoon_morning(self):
        # Un seul jour, afternoon → morning → 1 - 0.5 - 0.5 = 0
        result = compute_cp_days(
            date(2025, 1, 6), date(2025, 1, 6),
            start_period='afternoon', end_period='morning',
        )
        self.assertEqual(result, Decimal('0'))

    def test_jamais_negatif(self):
        # Résultat ne peut pas être négatif
        result = compute_cp_days(
            date(2025, 1, 6), date(2025, 1, 6),
            start_period='afternoon', end_period='morning',
        )
        self.assertGreaterEqual(result, Decimal('0'))


# ── parse_ai_planning_response ─────────────────────────────────────────────────

VALID_JSON_BLOCK = '''```json
{
  "weeks": {
    "A": [
      {"collaborator_id": 1, "day_of_week": 0, "start_time": "09:00", "end_time": "17:00"}
    ]
  },
  "violations": []
}
```'''

VALID_JSON_RAW = '''{
  "weeks": {
    "B": [
      {"collaborator_id": 2, "day_of_week": 1, "start_time": "8:30", "end_time": "17:00"}
    ]
  },
  "violations": []
}'''

TRAILING_COMMA_JSON = '''```json
{
  "weeks": {
    "A": [
      {"collaborator_id": 1, "day_of_week": 0, "start_time": "09:00", "end_time": "17:00",}
    ],
  },
  "violations": [],
}
```'''

MISSING_FIELD_JSON = '''```json
{
  "weeks": {
    "A": [
      {"collaborator_id": 1, "day_of_week": 0, "start_time": "09:00"}
    ]
  },
  "violations": []
}
```'''


class TestParseAiPlanningResponse(TestCase):

    def test_json_valide_bloc_backticks(self):
        result = parse_ai_planning_response(VALID_JSON_BLOCK)
        self.assertIn('weeks', result)
        self.assertIn('A', result['weeks'])
        self.assertEqual(len(result['weeks']['A']), 1)

    def test_json_valide_brut(self):
        result = parse_ai_planning_response(VALID_JSON_RAW)
        self.assertIn('B', result['weeks'])

    def test_normalisation_heure_sans_zero(self):
        # "8:30" doit être normalisé en "08:30:00"
        result = parse_ai_planning_response(VALID_JSON_RAW)
        shift = result['weeks']['B'][0]
        self.assertEqual(shift['start_time'], '08:30:00')

    def test_normalisation_heure_avec_zero(self):
        result = parse_ai_planning_response(VALID_JSON_BLOCK)
        shift = result['weeks']['A'][0]
        self.assertEqual(shift['start_time'], '09:00:00')
        self.assertEqual(shift['end_time'], '17:00:00')

    def test_virgule_trainante_corrigee(self):
        # Ne doit pas lever d'exception
        result = parse_ai_planning_response(TRAILING_COMMA_JSON)
        self.assertIn('A', result['weeks'])

    def test_json_manquant_leve_erreur(self):
        with self.assertRaises(AIParseError):
            parse_ai_planning_response("Voici le planning que j'ai généré pour vous.")

    def test_champ_manquant_leve_erreur(self):
        with self.assertRaises(AIParseError) as ctx:
            parse_ai_planning_response(MISSING_FIELD_JSON)
        self.assertIn('end_time', str(ctx.exception))

    def test_lettre_invalide_leve_erreur(self):
        bad_json = '{"weeks": {"Z": []}, "violations": []}'
        with self.assertRaises(AIParseError):
            parse_ai_planning_response(bad_json)

    def test_weeks_manquant_leve_erreur(self):
        with self.assertRaises(AIParseError):
            parse_ai_planning_response('{"violations": []}')

    def test_violations_absent_ajoute_liste_vide(self):
        json_sans_violations = '{"weeks": {"A": [{"collaborator_id":1,"day_of_week":0,"start_time":"09:00","end_time":"17:00"}]}}'
        result = parse_ai_planning_response(json_sans_violations)
        self.assertEqual(result['violations'], [])

    def test_texte_avec_json_integre(self):
        text = '''Voici le planning:

        {"weeks": {"A": [{"collaborator_id": 1, "day_of_week": 0, "start_time": "09:00", "end_time": "17:00"}]}, "violations": []}

        J'espère que cela vous convient.'''
        result = parse_ai_planning_response(text)
        self.assertIn('A', result['weeks'])

    def test_champ_inconnu_ignore(self):
        """Un champ supplémentaire dans un shift est ignoré sans exception."""
        json_avec_extra = '{"weeks": {"A": [{"collaborator_id": 1, "day_of_week": 0, "start_time": "09:00", "end_time": "17:00", "note": "extra"}]}, "violations": []}'
        result = parse_ai_planning_response(json_avec_extra)
        self.assertIn('A', result['weeks'])
        self.assertEqual(len(result['weeks']['A']), 1)

    def test_heure_invalide_25h_acceptee_par_normalise(self):
        """'25:00' est normalisé sans erreur (validation métier = côté modèle Django)."""
        json_bad_hour = '{"weeks": {"A": [{"collaborator_id": 1, "day_of_week": 0, "start_time": "25:00", "end_time": "17:00"}]}, "violations": []}'
        # parse_ai_planning_response ne valide pas la plage horaire — Django le fait
        result = parse_ai_planning_response(json_bad_hour)
        self.assertEqual(result['weeks']['A'][0]['start_time'], '25:00:00')


# ── 🆕 get_jours_feries — Pâques 2025 complet ─────────────────────────────────

class TestGetJoursFeries2025Complet(TestCase):
    """Vérifie Lundi de Pâques et Ascension 2025 (cas de régression courant)."""

    def test_lundi_paques_2025(self):
        # Pâques 2025 = 20 avril → lundi de Pâques = 21 avril
        feries = get_jours_feries(2025)
        self.assertIn(date(2025, 4, 21), feries)

    def test_ascension_2025(self):
        # Ascension = Pâques + 39j = 20 avril + 39 = 29 mai
        feries = get_jours_feries(2025)
        self.assertIn(date(2025, 5, 29), feries)

    def test_lundi_pentecote_2025(self):
        # Pentecôte = Pâques + 50j = 9 juin
        feries = get_jours_feries(2025)
        self.assertIn(date(2025, 6, 9), feries)
