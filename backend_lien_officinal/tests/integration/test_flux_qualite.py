"""
Intégration : flux qualité complet
NC : OPEN → assign (IN_PROGRESS) → close (CLOSED)
Procedure : créer (DRAFT) → publish (ACTIVE)
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy
from apps.quality.models import NonConformity, Procedure
from apps.team.models import Collaborator

_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_fq_{_counter}@test.com",
        password="pass",
        nom_officine="Pharmacie Qualité",
    )


def _make_titulaire(pharmacy):
    global _counter
    _counter += 1
    return Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name=f"Titu{_counter}",
        last_name="Qualite",
        role=Collaborator.Role.TITULAIRE,
        color="#556677",
        weekly_hours=35.0,
        can_manage_planning=True,
    )


def _pharmacy_client(pharmacy):
    """Token pharmacie directe — contourne les permissions qualité."""
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


class TestFluxNonConformite(TestCase):
    """
    Flux NC complet :
    1. Créer NC (statut OPEN)
    2. Assigner → statut IN_PROGRESS
    3. Clôturer → statut CLOSED
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.titulaire = _make_titulaire(self.pharmacy)
        self.client_pharma = _pharmacy_client(self.pharmacy)

    def test_flux_nc_complet(self):
        """NC OPEN → assign → IN_PROGRESS → close → CLOSED."""
        # 1. Créer une NC
        resp_create = self.client_pharma.post(
            '/api/quality/nonconformities/',
            {
                'title': 'Problème de stock',
                'description': 'Rupture de médicament critique',
                'severity': NonConformity.Severity.MAJOR,
            },
            format='json',
        )
        self.assertIn(resp_create.status_code, [200, 201])
        nc_id = resp_create.data['id']

        nc = NonConformity.objects.get(pk=nc_id)
        self.assertEqual(nc.status, NonConformity.Status.OPEN)

        # 2. Assigner au titulaire → IN_PROGRESS
        resp_assign = self.client_pharma.post(
            f'/api/quality/nonconformities/{nc_id}/assign/',
            {'assigned_to': self.titulaire.id},
            format='json',
        )
        self.assertEqual(resp_assign.status_code, 200)
        nc.refresh_from_db()
        self.assertEqual(nc.status, NonConformity.Status.IN_PROGRESS)
        self.assertEqual(nc.assigned_to, self.titulaire)

        # 3. Clôturer
        resp_close = self.client_pharma.post(
            f'/api/quality/nonconformities/{nc_id}/close/',
            {'resolution': 'Stock réapprovisionné, procédure mise à jour.'},
            format='json',
        )
        self.assertEqual(resp_close.status_code, 200)
        nc.refresh_from_db()
        self.assertEqual(nc.status, NonConformity.Status.CLOSED)
        self.assertIsNotNone(nc.closed_at)

    def test_close_nc_open_directement_400(self):
        """Clôturer une NC encore OPEN → 400."""
        resp_create = self.client_pharma.post(
            '/api/quality/nonconformities/',
            {
                'title': 'NC test close direct',
                'description': 'Test',
                'severity': NonConformity.Severity.MINOR,
            },
            format='json',
        )
        nc_id = resp_create.data['id']

        resp_close = self.client_pharma.post(
            f'/api/quality/nonconformities/{nc_id}/close/',
            {'resolution': 'Tentative prématurée'},
            format='json',
        )
        self.assertEqual(resp_close.status_code, 400)

        nc = NonConformity.objects.get(pk=nc_id)
        self.assertEqual(nc.status, NonConformity.Status.OPEN)


class TestFluxProcedure(TestCase):
    """
    Flux Procedure complet :
    1. Créer procédure (statut DRAFT)
    2. Publier → statut ACTIVE
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.client_pharma = _pharmacy_client(self.pharmacy)

    def test_flux_procedure_draft_puis_active(self):
        """Procedure DRAFT → publish → ACTIVE."""
        # 1. Créer une procédure
        resp_create = self.client_pharma.post(
            '/api/quality/procedures/',
            {
                'title': 'Procédure de nettoyage',
                'content': 'Description détaillée.',
                'reference': 'PROC-001',
            },
            format='json',
        )
        self.assertIn(resp_create.status_code, [200, 201])
        proc_id = resp_create.data['id']

        proc = Procedure.objects.get(pk=proc_id)
        self.assertEqual(proc.status, Procedure.Status.DRAFT)

        # 2. Publier
        resp_publish = self.client_pharma.post(
            f'/api/quality/procedures/{proc_id}/publish/',
            format='json',
        )
        self.assertEqual(resp_publish.status_code, 200)

        proc.refresh_from_db()
        self.assertEqual(proc.status, Procedure.Status.ACTIVE)

    def test_publier_procedure_deja_active_400(self):
        """Publier une procédure déjà ACTIVE → 400."""
        resp_create = self.client_pharma.post(
            '/api/quality/procedures/',
            {
                'title': 'Procédure doublon publish',
                'content': 'Test.',
                'reference': 'PROC-002',
            },
            format='json',
        )
        proc_id = resp_create.data['id']

        # Première publication → OK
        self.client_pharma.post(f'/api/quality/procedures/{proc_id}/publish/', format='json')

        # Deuxième publication → 400
        resp_second = self.client_pharma.post(
            f'/api/quality/procedures/{proc_id}/publish/',
            format='json',
        )
        self.assertEqual(resp_second.status_code, 400)
