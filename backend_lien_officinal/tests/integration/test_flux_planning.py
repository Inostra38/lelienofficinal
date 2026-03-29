"""
Intégration : flux planning complet
Créer template → Appliquer semaine → Publier → Vérifier récap hebdo calculé
"""

import datetime
from zoneinfo import ZoneInfo

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.core.models import Pharmacy
from apps.planning.calculator import week_summary
from apps.planning.models import Shift, WeekTemplate
from apps.team.models import Collaborator

TZ = ZoneInfo("Europe/Paris")
_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_fp_{_counter}@test.com",
        password="pass",
        nom_officine="Pharmacie Planning",
    )


def _make_collab(pharmacy, weekly_hours=35.0):
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name="Henri",
        last_name="Planning",
        role=Collaborator.Role.PREPARATEUR,
        color="#223344",
        weekly_hours=weekly_hours,
        can_manage_planning=True,
    )


def _collab_client(pharmacy, collab):
    client = APIClient()
    token = AccessToken.for_user(pharmacy)
    token['auth_type'] = 'collaborator'
    token['collaborator_id'] = collab.id
    token['can_manage_planning'] = True
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


class TestFluxPlanningComplet(TestCase):
    """
    Flux complet :
    1. Créer template A avec 5 shifts lun-ven 09h-17h
    2. Appliquer sur semaine 2026-W11
    3. Publier la semaine
    4. Vérifier le récap hebdo (40h planifiées, 5h sup TR1)
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.collab = _make_collab(self.pharmacy, weekly_hours=35.0)
        self.client = _collab_client(self.pharmacy, self.collab)

    def test_etape_1_creation_template(self):
        """POST template bulk-replace crée les TemplateShifts."""
        resp = self.client.post('/api/planning/templates/A/bulk-replace/', [
            {'collaborator_id': self.collab.id, 'day_of_week': i,
             'start_time': '09:00:00', 'end_time': '17:00:00'}
            for i in range(5)
        ], format='json')
        self.assertIn(resp.status_code, [200, 201])
        template = WeekTemplate.objects.get(pharmacy=self.pharmacy, letter='A')
        self.assertEqual(template.shifts.count(), 5)

    def test_flux_complet(self):
        """Test du flux en 4 étapes enchaînées."""
        # 1. Créer template
        self.client.post('/api/planning/templates/A/bulk-replace/', [
            {'collaborator_id': self.collab.id, 'day_of_week': i,
             'start_time': '09:00:00', 'end_time': '17:00:00'}
            for i in range(5)
        ], format='json')

        # 2. Appliquer la semaine 2026-W11 (lundi 9 mars)
        resp_apply = self.client.post(
            '/api/planning/templates/A/apply/',
            {'week': '2026-W11'},
            format='json',
        )
        self.assertEqual(resp_apply.status_code, 200)
        self.assertEqual(resp_apply.data['created'], 5)
        self.assertEqual(resp_apply.data['replaced'], 0)
        self.assertEqual(Shift.objects.filter(collaborator=self.collab).count(), 5)

        # 3. Publier
        resp_publish = self.client.post(
            '/api/planning/publish-week/',
            {'week': '2026-W11'},
            format='json',
        )
        self.assertEqual(resp_publish.status_code, 200)
        self.assertEqual(resp_publish.data['published'], 5)
        self.assertTrue(
            Shift.objects.filter(collaborator=self.collab, is_published=False).count() == 0
        )

        # 4. Vérifier récap hebdo via calculator
        result = week_summary(self.collab, datetime.date(2026, 3, 9))
        self.assertEqual(result['planned_h'], 40.0)   # 5 × 8h
        self.assertEqual(result['extra_h'], 5.0)      # 40h - 35h = 5h sup
        self.assertEqual(result['extra_h_25'], 5.0)   # ≤ 8h → tout en TR1
        self.assertEqual(result['extra_h_50'], 0.0)
        # Tous les shifts publiés ont le snapshot nom
        for s in Shift.objects.filter(collaborator=self.collab):
            self.assertIn('Henri', s.collaborator_snapshot)
