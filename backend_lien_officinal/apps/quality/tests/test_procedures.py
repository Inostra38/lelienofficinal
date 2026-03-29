"""
Tests ProcedureViewSet — workflow DRAFT→ACTIVE, transitions invalides,
création ProcedureVersion, downgrade automatique sur modification.
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import Pharmacy
from apps.quality.models import Procedure, ProcedureVersion

_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"proc_{_counter}@test.com",
        password="pass",
        nom_officine="Test Proc",
    )


def _pharmacy_client(pharmacy):
    """Token pharmacie directe → passe CanManageProcedures, CanPublishProcedures, etc."""
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def _make_procedure(pharmacy):
    return Procedure.objects.create(
        pharmacy=pharmacy,
        title="Procédure test",
        content="Contenu initial",
    )


# ── Workflow publication ──────────────────────────────────────────────────────

class TestProcedurePublicationWorkflow(TestCase):
    """Workflow DRAFT → publish → ACTIVE, avec création de ProcedureVersion."""

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.client = _pharmacy_client(self.pharmacy)

    def test_creation_statut_draft(self):
        """POST /api/quality/procedures/ → 201, statut DRAFT par défaut."""
        resp = self.client.post(
            '/api/quality/procedures/',
            {'title': 'Nouvelle procédure', 'content': 'Contenu'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['status'], 'draft')

    def test_publish_passe_en_active(self):
        """POST publish sur DRAFT → 200, status ACTIVE."""
        proc = _make_procedure(self.pharmacy)
        resp = self.client.post(
            f'/api/quality/procedures/{proc.id}/publish/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'active')

    def test_publish_cree_procedure_version(self):
        """Publication → 1 ProcedureVersion créée."""
        proc = _make_procedure(self.pharmacy)
        initial_version_count = ProcedureVersion.objects.filter(procedure=proc).count()
        self.client.post(f'/api/quality/procedures/{proc.id}/publish/', {}, format='json')
        self.assertEqual(
            ProcedureVersion.objects.filter(procedure=proc).count(),
            initial_version_count + 1,
        )

    def test_publish_active_400(self):
        """Publier une procédure déjà ACTIVE → 400."""
        proc = _make_procedure(self.pharmacy)
        self.client.post(f'/api/quality/procedures/{proc.id}/publish/', {}, format='json')
        resp = self.client.post(
            f'/api/quality/procedures/{proc.id}/publish/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_archive(self):
        """POST archive → status ARCHIVED."""
        proc = _make_procedure(self.pharmacy)
        self.client.post(f'/api/quality/procedures/{proc.id}/publish/', {}, format='json')
        resp = self.client.post(
            f'/api/quality/procedures/{proc.id}/archive/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'archived')


# ── Downgrade automatique sur modification ────────────────────────────────────

class TestProcedurePatchDowngrade(TestCase):
    """
    PATCH sur une procédure ACTIVE → elle repasse automatiquement en DRAFT.
    Garantit que les utilisateurs ne voient pas une procédure modifiée non revue.
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.client = _pharmacy_client(self.pharmacy)

    def test_patch_active_redevient_draft(self):
        """PATCH /api/quality/procedures/{id}/ sur proc ACTIVE → status redevient DRAFT."""
        proc = _make_procedure(self.pharmacy)
        # Publier d'abord
        self.client.post(f'/api/quality/procedures/{proc.id}/publish/', {}, format='json')
        proc.refresh_from_db()
        self.assertEqual(proc.status, Procedure.Status.ACTIVE)

        # Modifier le contenu
        resp = self.client.patch(
            f'/api/quality/procedures/{proc.id}/',
            {'content': 'Contenu modifié après publication'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'draft')

    def test_patch_draft_reste_draft(self):
        """PATCH sur proc DRAFT → status reste DRAFT (pas de downgrade supplémentaire)."""
        proc = _make_procedure(self.pharmacy)
        resp = self.client.patch(
            f'/api/quality/procedures/{proc.id}/',
            {'content': 'Contenu modifié'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'draft')


# ── Hiérarchie parent/child ───────────────────────────────────────────────────

class TestProcedureHierarchie(TestCase):
    """
    Procédures hiérarchiques : une procédure peut avoir un parent.
    - Création enfant avec parent → FK stockée
    - La liste inclut parent et enfant
    - Archivage du parent → les enfants sont promus en racine (parent=None)
    """

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.client = _pharmacy_client(self.pharmacy)
        self.parent = _make_procedure(self.pharmacy)
        self.child = Procedure.objects.create(
            pharmacy=self.pharmacy,
            title='Enfant',
            content='Sous-procédure',
            parent=self.parent,
        )

    def test_child_a_parent(self):
        """L'enfant a bien parent=parent.id après création."""
        self.assertEqual(self.child.parent_id, self.parent.id)

    def test_liste_inclut_parent_et_enfant(self):
        """GET /api/quality/procedures/ retourne les deux procédures."""
        resp = self.client.get('/api/quality/procedures/')
        self.assertEqual(resp.status_code, 200)
        ids = [p['id'] for p in resp.data]
        self.assertIn(self.parent.id, ids)
        self.assertIn(self.child.id, ids)

    def test_archivage_parent_promeut_enfants(self):
        """POST archive sur le parent → les enfants passent en racine (parent=None)."""
        self.client.post(
            f'/api/quality/procedures/{self.parent.id}/archive/',
            {},
            format='json',
        )
        self.child.refresh_from_db()
        self.assertIsNone(self.child.parent_id)
