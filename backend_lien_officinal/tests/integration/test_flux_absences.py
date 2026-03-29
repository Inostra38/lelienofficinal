"""
Intégration : flux absence CP complet
Poser une demande CP → Approuver → vérifier working_days_count
"""

import datetime

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.models import Pharmacy
from apps.planning.models import AbsenceRequest
from apps.team.models import Collaborator

_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_fab_{_counter}@test.com",
        password="pass",
        nom_officine="Pharmacie Absences",
    )


def _make_collab(pharmacy, can_manage=True):
    global _counter
    _counter += 1
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name=f"Alice{_counter}",
        last_name="Absence",
        role=Collaborator.Role.PREPARATEUR,
        color="#334455",
        weekly_hours=35.0,
        can_manage_planning=can_manage,
    )


def _collab_client(pharmacy, collab):
    client = APIClient()
    token = AccessToken.for_user(pharmacy)
    token['auth_type'] = 'collaborator'
    token['collaborator_id'] = collab.id
    token['can_manage_planning'] = collab.can_manage_planning
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


class TestFluxAbsenceCP(TestCase):
    """
    Flux complet :
    1. Poser une demande CP (lun 9 mars → ven 13 mars 2026)
    2. Approuver via PATCH review
    3. Vérifier working_days_count = 5.0 (pas de férié cette semaine)
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.manager = _make_collab(self.pharmacy, can_manage=True)
        self.preparateur = _make_collab(self.pharmacy, can_manage=False)
        self.manager_client = _collab_client(self.pharmacy, self.manager)
        self.prep_client = _collab_client(self.pharmacy, self.preparateur)

    def test_flux_cp_complet(self):
        """Demande CP → Approuver → working_days_count correcte."""
        # 1. Poser une demande CP (lun-ven 9-13 mars 2026, pas de férié)
        resp_create = self.prep_client.post(
            '/api/planning/absences/',
            {
                'collaborator_id': self.preparateur.id,
                'start_date': '2026-03-09',
                'end_date': '2026-03-13',
                'type': AbsenceRequest.AbsenceType.CP,
                'start_period': 'morning',
                'end_period': 'evening',
            },
            format='json',
        )
        self.assertIn(resp_create.status_code, [200, 201])
        # POST retourne {'absences': [...], 'skipped_days': N}
        absence_id = resp_create.data['absences'][0]['id']

        # Vérifier le statut initial
        absence = AbsenceRequest.objects.get(pk=absence_id)
        self.assertEqual(absence.status, AbsenceRequest.Status.PENDING)

        # 2. Approuver via le manager
        resp_review = self.manager_client.post(
            f'/api/planning/absences/{absence_id}/approve/',
            format='json',
        )
        self.assertEqual(resp_review.status_code, 200)

        # 3. Vérifier le statut et working_days_count
        absence.refresh_from_db()
        self.assertEqual(absence.status, AbsenceRequest.Status.APPROVED)
        # 5 jours ouvrés lun-ven sans férié
        self.assertEqual(float(absence.working_days_count), 5.0)

    def test_flux_cp_avec_ferie(self):
        """Semaine du lundi de Pâques 2026 (6 avril) : 4 jours ouvrés."""
        # Lun 6 avril 2026 = Lundi de Pâques → férié
        resp_create = self.prep_client.post(
            '/api/planning/absences/',
            {
                'collaborator_id': self.preparateur.id,
                'start_date': '2026-04-06',
                'end_date': '2026-04-10',
                'type': AbsenceRequest.AbsenceType.CP,
                'start_period': 'morning',
                'end_period': 'evening',
            },
            format='json',
        )
        self.assertIn(resp_create.status_code, [200, 201])
        absence_id = resp_create.data['absences'][0]['id']

        # Approuver
        self.manager_client.post(f'/api/planning/absences/{absence_id}/approve/', format='json')

        # Récupérer via GET pour avoir working_days_count calculé
        resp_get = self.manager_client.get('/api/planning/absences/')
        self.assertEqual(resp_get.status_code, 200)

        absences = resp_get.data if isinstance(resp_get.data, list) else resp_get.data.get('results', resp_get.data)
        # Trouver l'absence par ID
        target = next((a for a in absences if a['id'] == absence_id), None)
        self.assertIsNotNone(target)

        # working_days_count peut être sur plusieurs segments (si 1er mai croise)
        # Pour semaine du 6-10 avril : lundi férié → 4 jours
        total = sum(
            float(a['working_days_count'])
            for a in absences
            if a['id'] == absence_id and a.get('working_days_count') is not None
        )
        # Ou directement depuis l'objet DB
        absence = AbsenceRequest.objects.get(pk=absence_id)
        # La somme des segments doit donner 4.0 (lundi Pâques exclu)
        all_abs = AbsenceRequest.objects.filter(
            collaborator=self.preparateur,
            start_date__gte=datetime.date(2026, 4, 6),
            end_date__lte=datetime.date(2026, 4, 10),
        )
        total_days = sum(
            float(a.working_days_count)
            for a in all_abs
            if a.working_days_count is not None
        )
        self.assertEqual(total_days, 4.0)

    def test_flux_cp_rejet(self):
        """Demande CP refusée → statut REJECTED."""
        resp_create = self.prep_client.post(
            '/api/planning/absences/',
            {
                'collaborator_id': self.preparateur.id,
                'start_date': '2026-03-16',
                'end_date': '2026-03-18',
                'type': AbsenceRequest.AbsenceType.CP,
                'start_period': 'morning',
                'end_period': 'evening',
            },
            format='json',
        )
        self.assertIn(resp_create.status_code, [200, 201])
        absence_id = resp_create.data['absences'][0]['id']

        resp_reject = self.manager_client.post(
            f'/api/planning/absences/{absence_id}/reject/',
            format='json',
        )
        self.assertEqual(resp_reject.status_code, 200)

        absence = AbsenceRequest.objects.get(pk=absence_id)
        self.assertEqual(absence.status, AbsenceRequest.Status.REJECTED)

    def test_flux_maladie_working_days_null(self):
        """Type maladie → working_days_count = null."""
        resp_create = self.prep_client.post(
            '/api/planning/absences/',
            {
                'collaborator_id': self.preparateur.id,
                'start_date': '2026-03-09',
                'end_date': '2026-03-13',
                'type': AbsenceRequest.AbsenceType.MALADIE,
                'start_period': 'morning',
                'end_period': 'evening',
            },
            format='json',
        )
        self.assertIn(resp_create.status_code, [200, 201])
        absence_id = resp_create.data['absences'][0]['id']

        absence = AbsenceRequest.objects.get(pk=absence_id)
        self.assertIsNone(absence.working_days_count)
