"""
Tests de performance — pas de requêtes N+1.

Vérifient que les fonctions de calcul batch utilisent bien des requêtes groupées
et que leur coût SQL reste constant quelle que soit la taille de l'équipe.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy
from apps.planning.calculator import pharmacy_week_summary
from apps.planning.models import Shift, TemplateShift, WeekTemplate
from apps.planning.paye_analytics import compute_paye_summary
from apps.team.models import Collaborator

TZ = ZoneInfo("Europe/Paris")
_counter = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"perf_{_counter}@test.com",
        password="pass",
        nom_officine="Perf",
    )


def _make_collab(pharmacy, n=0):
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name=f"Collab{n}",
        last_name="Perf",
        role=Collaborator.Role.PREPARATEUR,
        color="#aabbcc",
        weekly_hours=35,
    )


def _make_shift(collab, day):
    """Crée un shift publié de 8h–16h un jour donné."""
    return Shift.objects.create(
        collaborator=collab,
        start_datetime=datetime(day.year, day.month, day.day, 8, 0, tzinfo=TZ),
        end_datetime=datetime(day.year, day.month, day.day, 16, 0, tzinfo=TZ),
        is_published=True,
    )


def _pharmacy_client(pharmacy):
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


# ── pharmacy_week_summary — N+1 ───────────────────────────────────────────────

class TestPharmacyWeekSummaryNoN1(TestCase):
    """
    pharmacy_week_summary effectue exactement 5 requêtes batch,
    quelle que soit la taille de l'équipe.
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.monday = date(2026, 3, 9)  # semaine W11
        for i in range(20):
            c = _make_collab(self.pharmacy, i)
            _make_shift(c, self.monday)

    def test_5_queries_avec_20_collaborateurs(self):
        with self.assertNumQueries(5):
            result = pharmacy_week_summary(self.pharmacy, self.monday)
        self.assertEqual(len(result), 20)

    def test_meme_cout_equipe_vide(self):
        """Même structure de 5 requêtes même sans données (short-circuit sur all_collabs vide)."""
        empty_pharmacy = _make_pharmacy()
        # Quand all_collabs est vide, la fonction retourne [] après 2 requêtes.
        with self.assertNumQueries(2):
            result = pharmacy_week_summary(empty_pharmacy, self.monday)
        self.assertEqual(result, [])


# ── compute_paye_summary — N+1 ────────────────────────────────────────────────

class TestComputePayeSummaryBoundedQueries(TestCase):
    """
    compute_paye_summary effectue exactement 10 requêtes bulk via _fetch_indexes,
    quelle que soit la taille de l'équipe.
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        monday = date(2026, 3, 9)
        for i in range(10):
            c = _make_collab(self.pharmacy, i)
            _make_shift(c, monday)

    def test_10_queries_avec_10_collaborateurs(self):
        # Mois en cours (mars 2026) → pas de cache → exactement les requêtes de _fetch_indexes
        with self.assertNumQueries(10):
            result = compute_paye_summary(self.pharmacy, 2026, 3)
        self.assertEqual(len(result['collaborateurs']), 10)

    def test_meme_cout_equipe_vide(self):
        """Aucun collaborateur actif → 9 requêtes (ContractHistory skippée car IN () vide)."""
        empty_pharmacy = _make_pharmacy()
        # _fetch_indexes : 1 (collaborators) + 8 bulk sur ensemble vide = 9 requêtes
        # ContractHistory.filter(collaborator_id__in=[]) → Django ne l'exécute pas
        with self.assertNumQueries(9):
            result = compute_paye_summary(empty_pharmacy, 2026, 3)
        self.assertEqual(result['collaborateurs'], [])


# ── TemplateApplyView — création de masse ─────────────────────────────────────

class TestTemplateApplyBulk50Shifts(TestCase):
    """
    TemplateApplyView crée 50 shifts en un seul appel API
    (10 collaborateurs × 5 jours, semaine vide).
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        template, _ = WeekTemplate.objects.get_or_create(
            pharmacy=self.pharmacy, letter='A'
        )
        for i in range(10):
            c = _make_collab(self.pharmacy, i)
            for day_of_week in range(5):  # Lun–Ven
                TemplateShift.objects.create(
                    template=template,
                    collaborator=c,
                    day_of_week=day_of_week,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                )
        self.client = _pharmacy_client(self.pharmacy)

    def test_50_shifts_crees_en_un_appel(self):
        resp = self.client.post(
            '/api/planning/templates/A/apply/',
            {'week': '2026-W11'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['created'], 50)
        self.assertEqual(resp.data['skipped'], 0)
        self.assertEqual(resp.data['replaced'], 0)
        self.assertEqual(Shift.objects.count(), 50)

    def test_apply_avec_force_remplace_50_shifts(self):
        """Deuxième apply avec force=True → replaced=10 (paires), created=50 (nouveaux shifts)."""
        self.client.post(
            '/api/planning/templates/A/apply/',
            {'week': '2026-W11'},
            format='json',
        )
        resp = self.client.post(
            '/api/planning/templates/A/apply/',
            {'week': '2026-W11', 'force': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['replaced'], 50)
        self.assertEqual(resp.data['created'], 50)
        self.assertEqual(Shift.objects.count(), 50)
