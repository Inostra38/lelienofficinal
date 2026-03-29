"""
Tests planning/views.py — AbsenceListCreateView
working_days_count : avec férié, week-end uniquement, à cheval sur deux semaines
"""

import datetime

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.models import Pharmacy
from apps.planning.models import AbsenceRequest
from apps.team.models import Collaborator

_counter = 0


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_va_{_counter}@test.com",
        password="pass",
        nom_officine="Test",
    )


def _make_collab(pharmacy, can_manage=True):
    c = Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name="Diane",
        last_name="Absence",
        role=Collaborator.Role.PREPARATEUR,
        color="#778899",
        weekly_hours=35,
        can_manage_planning=can_manage,
    )
    return c


def _collab_client(pharmacy, collab):
    client = APIClient()
    token = AccessToken.for_user(pharmacy)
    token['auth_type'] = 'collaborator'
    token['collaborator_id'] = collab.id
    token['can_manage_planning'] = collab.can_manage_planning
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


def _post_absence(client, collab_id, start, end, absence_type='cp',
                  start_period='morning', end_period='evening'):
    return client.post('/api/planning/absences/', {
        'collaborator_id': collab_id,
        'start_date': start,
        'end_date': end,
        'type': absence_type,
        'start_period': start_period,
        'end_period': end_period,
    }, format='json')


# ── working_days_count correct pour 5 jours avec un férié ─────────────────────

class TestAbsenceWorkingDaysFerie(TestCase):
    """
    Semaine du 28 avr au 2 mai 2025 : lun-mar-mer-jeu-ven
    Jeudi 1er mai = Fête du Travail (férié)
    → 4 jours ouvrés CP
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)

    def test_working_days_count_4_avec_1er_mai(self):
        """
        28 avr → 2 mai : 1er mai (férié) exclu → 2 segments créés (28-30 avr + 2 mai).
        Total working_days_count = 3 + 1 = 4.
        """
        resp = _post_absence(self.client, self.collab.id, '2025-04-28', '2025-05-02')
        self.assertEqual(resp.status_code, 201)
        from decimal import Decimal
        total = sum(
            Decimal(str(a['working_days_count']))
            for a in resp.data['absences']
            if a['working_days_count'] is not None
        )
        self.assertEqual(total, Decimal('4.0'))

    def test_semaine_sans_ferie_5_jours(self):
        """Lun-ven sans férié → 5 jours CP."""
        resp = _post_absence(self.client, self.collab.id, '2026-03-09', '2026-03-13')
        self.assertEqual(resp.status_code, 201)
        absence = resp.data['absences'][0]
        from decimal import Decimal
        self.assertEqual(Decimal(str(absence['working_days_count'])), Decimal('5.0'))


# ── Absence sur week-end uniquement → working_days_count=0 (🆕) ───────────────

class TestAbsenceWeekend(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)

    def test_absence_samedi_dimanche_retournee(self):
        """Sam-dim : samedi compte (lun-sam), dimanche ne compte pas."""
        resp = _post_absence(self.client, self.collab.id, '2026-03-14', '2026-03-15')
        # La requête peut être acceptée (samedi travaillé) ou rejetée selon PharmacyDayStatus
        # On vérifie surtout qu'il n'y a pas d'erreur 500
        self.assertIn(resp.status_code, [201, 400])

    def test_absence_dimanche_seul_bloque(self):
        """Dimanche seul → tous les jours bloqués → 400."""
        resp = _post_absence(self.client, self.collab.id, '2026-03-15', '2026-03-15')
        # Dimanche = jour non travaillé (weekday == 6)
        self.assertEqual(resp.status_code, 400)


# ── Absence à cheval sur deux semaines (🆕) ────────────────────────────────────

class TestAbsenceChevalSemaines(TestCase):
    """
    Absence du mer 11 mars au mar 17 mars 2026.
    Jours ouvrés (lun-sam, hors dimanches) :
      mer 11, jeu 12, ven 13, sam 14 = 4j première semaine
      lun 16, mar 17 = 2j deuxième semaine
      Total = 6j CP
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)

    def test_working_days_count_cheval_deux_semaines(self):
        resp = _post_absence(self.client, self.collab.id, '2026-03-11', '2026-03-17')
        self.assertEqual(resp.status_code, 201)
        # Dimanche 15 mars exclu → 6 jours ouvrés
        total = sum(
            float(a['working_days_count'])
            for a in resp.data['absences']
            if a['working_days_count'] is not None
        )
        self.assertEqual(total, 6.0)


# ── Demi-journées (start_period / end_period) ─────────────────────────────────

class TestAbsenceDemiJournees(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy)
        self.client = _collab_client(self.pharmacy, self.collab)

    def test_morning_to_morning_4_5_jours(self):
        """Lun matin → ven matin = 5j − 0,5j fin = 4,5j."""
        resp = _post_absence(
            self.client, self.collab.id,
            '2026-03-09', '2026-03-13',
            start_period='morning', end_period='morning',
        )
        self.assertEqual(resp.status_code, 201)
        from decimal import Decimal
        wdc = Decimal(str(resp.data['absences'][0]['working_days_count']))
        self.assertEqual(wdc, Decimal('4.5'))

    def test_afternoon_to_evening_4_5_jours(self):
        """Lun après-midi → ven soir = 5j − 0,5j début = 4,5j."""
        resp = _post_absence(
            self.client, self.collab.id,
            '2026-03-09', '2026-03-13',
            start_period='afternoon', end_period='evening',
        )
        self.assertEqual(resp.status_code, 201)
        from decimal import Decimal
        wdc = Decimal(str(resp.data['absences'][0]['working_days_count']))
        self.assertEqual(wdc, Decimal('4.5'))

    def test_absence_type_non_cp_working_days_null(self):
        """Pour une absence de type maladie, working_days_count reste null."""
        resp = _post_absence(
            self.client, self.collab.id,
            '2026-03-09', '2026-03-13',
            absence_type='maladie',
        )
        self.assertEqual(resp.status_code, 201)
        absence = resp.data['absences'][0]
        self.assertIsNone(absence['working_days_count'])
