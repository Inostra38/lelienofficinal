"""Autorisations qualité (audit 2026-07-09, lot sécurité).

S01/Q11 — status/version de procédure ne doivent pas être modifiables par PATCH
          direct (contournement du workflow de publication).
S02     — NonConformityViewSet exposait update/partial_update/destroy en
          IsAuthenticated seul → tout collaborateur pouvait modifier/supprimer/
          clôturer une NC en contournant les actions gardées.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.models import Pharmacy
from apps.quality.models import NonConformity, Procedure
from apps.team.models import Collaborator

_n = 0


def _pharma():
    global _n
    _n += 1
    return Pharmacy.objects.create_user(email=f"qz_{_n}@t.com", password="x", nom_officine="Ph")


def _collab(pharmacy, role=Collaborator.Role.PREPARATEUR, **perms):
    c = Collaborator.objects.create(
        pharmacy=pharmacy, first_name="A", last_name="B", role=role,
        color="#112233", weekly_hours=35, **perms,
    )
    c.set_pin("1234")
    c.save()
    return c


def _collab_client(pharmacy, collaborator):
    """JWT collaborateur (claims auth_type + collaborator_id), comme /api/team/login/."""
    token = AccessToken.for_user(pharmacy)
    token['auth_type'] = 'collaborator'
    token['collaborator_id'] = collaborator.id
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class TestProcedureStatusReadOnly(TestCase):
    def test_patch_status_ignore(self):
        pharma = _pharma()
        editeur = _collab(pharma, can_manage_procedures=True)  # peut éditer, PAS publier
        proc = Procedure.objects.create(
            pharmacy=pharma, title="P", status=Procedure.Status.DRAFT,
        )
        resp = _collab_client(pharma, editeur).patch(
            f'/api/quality/procedures/{proc.id}/',
            {'status': Procedure.Status.ACTIVE, 'title': 'P modifié'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        proc.refresh_from_db()
        self.assertEqual(proc.status, Procedure.Status.DRAFT)  # status ignoré (read-only)
        self.assertEqual(proc.title, 'P modifié')              # le reste passe

    def test_patch_version_ignore(self):
        pharma = _pharma()
        editeur = _collab(pharma, can_manage_procedures=True)
        proc = Procedure.objects.create(pharmacy=pharma, title="P", version=1)
        resp = _collab_client(pharma, editeur).patch(
            f'/api/quality/procedures/{proc.id}/', {'version': 99}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        proc.refresh_from_db()
        self.assertEqual(proc.version, 1)


class TestNonConformityWriteAuthz(TestCase):
    def setUp(self):
        self.pharma = _pharma()
        self.nc = NonConformity.objects.create(
            pharmacy=self.pharma, title="NC", description="desc", severity='minor',
            status=NonConformity.Status.OPEN,
        )

    def test_prepa_sans_droit_ne_peut_pas_supprimer(self):
        prepa = _collab(self.pharma)  # aucun droit qualité
        resp = _collab_client(self.pharma, prepa).delete(f'/api/quality/nonconformities/{self.nc.id}/')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(NonConformity.objects.filter(id=self.nc.id).exists())

    def test_prepa_sans_droit_ne_peut_pas_cloturer_par_patch(self):
        prepa = _collab(self.pharma)
        resp = _collab_client(self.pharma, prepa).patch(
            f'/api/quality/nonconformities/{self.nc.id}/',
            {'status': NonConformity.Status.CLOSED}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.nc.refresh_from_db()
        self.assertEqual(self.nc.status, NonConformity.Status.OPEN)

    def test_manager_qualite_peut_modifier_mais_status_reste_read_only(self):
        manager = _collab(self.pharma, can_manage_quality=True)
        resp = _collab_client(self.pharma, manager).patch(
            f'/api/quality/nonconformities/{self.nc.id}/',
            {'title': 'NC renommée', 'status': NonConformity.Status.CLOSED}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.nc.refresh_from_db()
        self.assertEqual(self.nc.title, 'NC renommée')            # écriture autorisée
        self.assertEqual(self.nc.status, NonConformity.Status.OPEN)  # status read-only
