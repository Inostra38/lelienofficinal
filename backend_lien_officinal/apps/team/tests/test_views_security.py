"""Non-régression sur le correctif C1 (escalade de privilèges via l'API équipe).

`role` et les `can_manage_*` restent des champs writable du CollaboratorSerializer :
la protection vit entièrement dans CollaboratorViewSet.update/destroy/update_permissions.
Un refactor qui déplacerait ces vues rouvrirait la faille sans bruit — d'où ces tests.

Rappel du modèle : Collaborator.save() force tous les droits à True pour un Titulaire.
Se promouvoir Titulaire équivaut donc à s'accorder toutes les permissions d'un coup.
"""
import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.core.models import Pharmacy
from apps.team.models import Collaborator

_counter = 0


def _make_pharmacy():
    global _counter
    _counter += 1
    return Pharmacy.objects.create_user(
        email=f"pharma_sec_{_counter}@test.com",
        password="pass",
        nom_officine="Test",
    )


def _make_collab(pharmacy, role=Collaborator.Role.PREPARATEUR, can_manage_team=False, **kwargs):
    collab = Collaborator.objects.create(
        pharmacy=pharmacy,
        first_name=kwargs.pop('first_name', 'Bob'),
        last_name=kwargs.pop('last_name', 'Test'),
        role=role,
        color="#112233",
        weekly_hours=35,
        can_manage_team=can_manage_team,
        **kwargs,
    )
    collab.set_pin("1234")
    collab.save()
    return collab


def _pharmacy_client(pharmacy):
    """JWT de pharmacie, sans identité collaborateur (auth_type absent)."""
    client = APIClient()
    refresh = RefreshToken.for_user(pharmacy)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def _collab_client(pharmacy, collaborator):
    """JWT collaborateur, forgé comme le fait /api/team/login/ (team/views.py:236-248)."""
    token = AccessToken.for_user(pharmacy)
    token['auth_type'] = 'collaborator'
    token['collaborator_id'] = collaborator.id
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class TestCollaboratorUpdateSecurity(TestCase):
    """PATCH/PUT /api/team/{id}/ — le cœur du correctif C1."""

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.titulaire = _make_collab(self.pharmacy, role=Collaborator.Role.TITULAIRE, last_name="Titu")
        self.manager = _make_collab(self.pharmacy, can_manage_team=True, last_name="Manager")
        self.simple = _make_collab(self.pharmacy, last_name="Simple")

    def _patch(self, client, target, data):
        return client.patch(f'/api/team/{target.id}/', data, format='json')

    def test_jwt_pharmacie_sans_identite_collaborateur_403(self):
        # _get_collaborator renvoie None → _check_permission refuse.
        resp = self._patch(_pharmacy_client(self.pharmacy), self.simple, {'last_name': 'Pirate'})
        self.assertEqual(resp.status_code, 403)
        self.simple.refresh_from_db()
        self.assertEqual(self.simple.last_name, 'Simple')

    def test_sans_can_manage_team_403(self):
        resp = self._patch(_collab_client(self.pharmacy, self.simple), self.manager, {'last_name': 'Pirate'})
        self.assertEqual(resp.status_code, 403)

    def test_auto_promotion_titulaire_interdite(self):
        """C1 : le scénario d'escalade. Se promouvoir Titulaire = tous les droits."""
        client = _collab_client(self.pharmacy, self.manager)
        resp = self._patch(client, self.manager, {'role': Collaborator.Role.TITULAIRE})
        self.assertEqual(resp.status_code, 403)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.role, Collaborator.Role.PREPARATEUR)
        self.assertFalse(self.manager.can_manage_account)

    def test_auto_octroi_de_permission_interdit(self):
        client = _collab_client(self.pharmacy, self.manager)
        resp = self._patch(client, self.manager, {'can_manage_account': True})
        self.assertEqual(resp.status_code, 403)
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.can_manage_account)

    def test_auto_modification_pin_interdite(self):
        client = _collab_client(self.pharmacy, self.manager)
        ancien_hash = self.manager.pin_hash
        resp = self._patch(client, self.manager, {'pin': '9999'})
        self.assertEqual(resp.status_code, 403)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.pin_hash, ancien_hash)

    def test_put_auto_promotion_interdite(self):
        """partial_update() délègue à update() ; on vérifie que PUT passe par la même garde."""
        client = _collab_client(self.pharmacy, self.manager)
        resp = client.put(f'/api/team/{self.manager.id}/', {
            'first_name': 'Bob', 'last_name': 'Manager', 'color': '#112233',
            'weekly_hours': 35, 'role': Collaborator.Role.TITULAIRE,
        }, format='json')
        self.assertEqual(resp.status_code, 403)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.role, Collaborator.Role.PREPARATEUR)

    def test_non_titulaire_ne_peut_pas_modifier_un_titulaire(self):
        client = _collab_client(self.pharmacy, self.manager)
        resp = self._patch(client, self.titulaire, {'last_name': 'Pirate'})
        self.assertEqual(resp.status_code, 403)
        self.titulaire.refresh_from_db()
        self.assertEqual(self.titulaire.last_name, 'Titu')

    def test_titulaire_peut_modifier_un_autre_titulaire(self):
        autre_titulaire = _make_collab(self.pharmacy, role=Collaborator.Role.TITULAIRE, last_name="Titu2")
        client = _collab_client(self.pharmacy, self.titulaire)
        resp = self._patch(client, autre_titulaire, {'last_name': 'Renomme'})
        self.assertEqual(resp.status_code, 200)
        autre_titulaire.refresh_from_db()
        self.assertEqual(autre_titulaire.last_name, 'Renomme')

    def test_manager_peut_modifier_un_autre_collaborateur(self):
        """Chemin nominal : la garde ne doit pas casser l'usage légitime."""
        client = _collab_client(self.pharmacy, self.manager)
        resp = self._patch(client, self.simple, {'last_name': 'Renomme'})
        self.assertEqual(resp.status_code, 200)
        self.simple.refresh_from_db()
        self.assertEqual(self.simple.last_name, 'Renomme')

    def test_collaborateur_autre_pharmacie_404(self):
        autre_pharmacie = _make_pharmacy()
        cible = _make_collab(autre_pharmacie, last_name="Etranger")
        client = _collab_client(self.pharmacy, self.titulaire)
        resp = self._patch(client, cible, {'last_name': 'Pirate'})
        self.assertEqual(resp.status_code, 404)
        cible.refresh_from_db()
        self.assertEqual(cible.last_name, 'Etranger')


class TestCollaboratorPermissionsEndpoint(TestCase):
    """PATCH /api/team/{id}/permissions/"""

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.titulaire = _make_collab(self.pharmacy, role=Collaborator.Role.TITULAIRE, last_name="Titu")
        self.manager = _make_collab(self.pharmacy, can_manage_team=True, last_name="Manager")
        self.simple = _make_collab(self.pharmacy, last_name="Simple")

    def _patch_perms(self, client, target, data):
        return client.patch(f'/api/team/{target.id}/permissions/', data, format='json')

    def test_sans_can_manage_team_403(self):
        resp = self._patch_perms(_collab_client(self.pharmacy, self.simple), self.manager,
                                 {'can_manage_account': True})
        self.assertEqual(resp.status_code, 403)
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.can_manage_account)

    def test_auto_modification_de_ses_permissions_403(self):
        client = _collab_client(self.pharmacy, self.manager)
        resp = self._patch_perms(client, self.manager, {'can_manage_account': True})
        self.assertEqual(resp.status_code, 403)
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.can_manage_account)

    def test_permissions_du_titulaire_non_modifiables(self):
        client = _collab_client(self.pharmacy, self.titulaire)
        resp = self._patch_perms(client, self.titulaire, {'can_manage_team': False})
        self.assertEqual(resp.status_code, 403)

    def test_manager_modifie_les_permissions_dun_autre(self):
        client = _collab_client(self.pharmacy, self.manager)
        resp = self._patch_perms(client, self.simple, {'can_manage_planning': True})
        self.assertEqual(resp.status_code, 200)
        self.simple.refresh_from_db()
        self.assertTrue(self.simple.can_manage_planning)

    def test_collaborateur_autre_pharmacie_404(self):
        autre_pharmacie = _make_pharmacy()
        cible = _make_collab(autre_pharmacie)
        client = _collab_client(self.pharmacy, self.titulaire)
        resp = self._patch_perms(client, cible, {'can_manage_account': True})
        self.assertEqual(resp.status_code, 404)
        cible.refresh_from_db()
        self.assertFalse(cible.can_manage_account)


class TestCollaboratorDestroySecurity(TestCase):
    """DELETE /api/team/{id}/ — archivage logique."""

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.titulaire = _make_collab(self.pharmacy, role=Collaborator.Role.TITULAIRE, last_name="Titu")
        self.manager = _make_collab(self.pharmacy, can_manage_team=True, last_name="Manager")
        self.simple = _make_collab(self.pharmacy, last_name="Simple")

    def test_sans_can_manage_team_403(self):
        client = _collab_client(self.pharmacy, self.simple)
        resp = client.delete(f'/api/team/{self.manager.id}/')
        self.assertEqual(resp.status_code, 403)
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.is_active)

    def test_auto_suppression_403(self):
        client = _collab_client(self.pharmacy, self.manager)
        resp = client.delete(f'/api/team/{self.manager.id}/')
        self.assertEqual(resp.status_code, 403)
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.is_active)

    def test_suppression_du_titulaire_403(self):
        client = _collab_client(self.pharmacy, self.titulaire)
        autre_titulaire = _make_collab(self.pharmacy, role=Collaborator.Role.TITULAIRE, last_name="Titu2")
        resp = client.delete(f'/api/team/{autre_titulaire.id}/')
        self.assertEqual(resp.status_code, 403)
        autre_titulaire.refresh_from_db()
        self.assertTrue(autre_titulaire.is_active)

    def test_archivage_logique_204(self):
        client = _collab_client(self.pharmacy, self.manager)
        avant = timezone.now() - datetime.timedelta(seconds=1)
        resp = client.delete(f'/api/team/{self.simple.id}/')
        self.assertEqual(resp.status_code, 204)
        self.simple.refresh_from_db()
        self.assertFalse(self.simple.is_active)
        self.assertIsNotNone(self.simple.archived_at)
        self.assertGreater(self.simple.archived_at, avant)

    def test_collaborateur_autre_pharmacie_404(self):
        autre_pharmacie = _make_pharmacy()
        cible = _make_collab(autre_pharmacie)
        client = _collab_client(self.pharmacy, self.titulaire)
        resp = client.delete(f'/api/team/{cible.id}/')
        self.assertEqual(resp.status_code, 404)
        cible.refresh_from_db()
        self.assertTrue(cible.is_active)
