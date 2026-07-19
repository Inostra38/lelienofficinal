"""
Tests core/views.py — Register, JWT (forgé/expiré/refresh), endpoints protégés, vérification email
"""

import json
import time
import uuid
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

from apps.core.models import Pharmacy

_counter = 0


def _make_pharmacy(email=None):
    global _counter
    _counter += 1
    e = email or f"pharma_auth_{_counter}@test.com"
    return Pharmacy.objects.create_user(
        email=e,
        password="secret123",
        nom_officine="Officine Test",
    )


# ── Register ──────────────────────────────────────────────────────────────────

class TestRegisterView(TestCase):

    @patch('apps.core.tasks.send_verification_email_task')
    def test_register_succes_201(self, _mock_email):
        resp = self.client.post('/api/auth/register/', {
            'email': 'nouveau@test.com',
            'password': 'motdepasse1',
            'password_confirm': 'motdepasse1',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('access', resp.data)
        # Le refresh token est désormais dans un cookie HttpOnly
        self.assertIn('refresh_token', resp.cookies)
        self.assertTrue(resp.cookies['refresh_token']['httponly'])

    def test_register_email_existant_400(self):
        _make_pharmacy(email='existant@test.com')
        resp = self.client.post('/api/auth/register/', {
            'email': 'existant@test.com',
            'password': 'motdepasse1',
            'password_confirm': 'motdepasse1',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    @patch('apps.core.tasks.send_verification_email_task')
    def test_register_email_domaine_normalise_minuscule(self, _mock_email):
        """Django normalize_email met le domaine en minuscule (pas la partie locale)."""
        resp = self.client.post('/api/auth/register/', {
            'email': 'MAJuscule@TEST.COM',
            'password': 'motdepasse1',
            'password_confirm': 'motdepasse1',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 201)
        # normalize_email : domaine en minuscule, partie locale conservée
        self.assertTrue(Pharmacy.objects.filter(email='MAJuscule@test.com').exists())

    def test_register_password_mismatch_400(self):
        resp = self.client.post('/api/auth/register/', {
            'email': 'mismatch@test.com',
            'password': 'motdepasse1',
            'password_confirm': 'autrechose',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_register_mot_de_passe_trop_court_400(self):
        resp = self.client.post('/api/auth/register/', {
            'email': 'court@test.com',
            'password': '123',
            'password_confirm': '123',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 400)


# ── Endpoints protégés ────────────────────────────────────────────────────────

class TestEndpointsProtected(TestCase):

    PROTECTED_ENDPOINTS = [
        '/api/team/',
        '/api/planning/shifts/',
        '/api/pharmacy/me/',
    ]

    def test_sans_token_401(self):
        client = APIClient()
        for url in self.PROTECTED_ENDPOINTS:
            with self.subTest(url=url):
                resp = client.get(url)
                self.assertEqual(resp.status_code, 401, f"Expected 401 for {url}")

    def test_avec_token_valide_pas_401(self):
        pharmacy = _make_pharmacy()
        client = APIClient()
        refresh = RefreshToken.for_user(pharmacy)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        resp = client.get('/api/pharmacy/me/')
        self.assertNotEqual(resp.status_code, 401)


# ── JWT forgé / expiré ────────────────────────────────────────────────────────

class TestJWTSecurity(TestCase):

    def setUp(self):
        self.pharmacy = _make_pharmacy()
        self.client = APIClient()

    def test_jwt_forge_401(self):
        """Un token avec signature invalide retourne 401, pas 500."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.FAUX_SIGNATURE")
        resp = self.client.get('/api/pharmacy/me/')
        self.assertEqual(resp.status_code, 401)

    def test_jwt_expire_401(self):
        """Un token expiré retourne 401."""
        from rest_framework_simplejwt.tokens import AccessToken
        from datetime import timedelta
        token = AccessToken.for_user(self.pharmacy)
        # Forcer l'expiration dans le passé
        token.set_exp(lifetime=timedelta(seconds=-1))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
        resp = self.client.get('/api/pharmacy/me/')
        self.assertEqual(resp.status_code, 401)

    def test_jwt_invalide_pas_500(self):
        """Un token malformé retourne 401, pas une erreur serveur 500."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer pas.un.jwt")
        resp = self.client.get('/api/pharmacy/me/')
        self.assertIn(resp.status_code, [401, 403])

    def test_token_refresh_valide(self):
        """Un refresh token valide (via cookie) génère un nouvel access token."""
        refresh = RefreshToken.for_user(self.pharmacy)
        self.client.cookies['refresh_token'] = str(refresh)
        resp = self.client.post('/api/token/refresh/', content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)

    def test_token_refresh_invalide_401(self):
        """Un refresh token invalide/forgé retourne 401."""
        self.client.cookies['refresh_token'] = 'token.invalide.forge'
        resp = self.client.post('/api/token/refresh/', content_type='application/json')
        self.assertEqual(resp.status_code, 401)

    def test_login_succes_retourne_tokens(self):
        """POST /api/token/ avec credentials valides retourne access dans le body et refresh en cookie."""
        resp = self.client.post('/api/token/', {
            'email': self.pharmacy.email,
            'password': 'secret123',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)
        self.assertNotIn('refresh', resp.data)
        self.assertIn('refresh_token', resp.cookies)

    def test_login_mauvais_mdp_401(self):
        resp = self.client.post('/api/token/', {
            'email': self.pharmacy.email,
            'password': 'mauvais',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 401)


# ── HttpOnly cookie — couverture exhaustive ───────────────────────────────────

class TestHttpOnlyCookies(TestCase):
    """Vérifie le comportement complet de la stratégie cookie HttpOnly (C69)."""

    def setUp(self):
        self.pharmacy = _make_pharmacy()

    def _login(self):
        return self.client.post('/api/token/', {
            'email': self.pharmacy.email,
            'password': 'secret123',
        }, content_type='application/json')

    # ── session_info : présence, non-HttpOnly, contenu JSON ───────────────────

    @patch('apps.core.tasks.send_verification_email_task')
    def test_register_set_session_info_cookie(self, _mock_email):
        """Register pose également le cookie session_info."""
        resp = self.client.post('/api/auth/register/', {
            'email': 'cookie_si@test.com',
            'password': 'motdepasse1',
            'password_confirm': 'motdepasse1',
        }, content_type='application/json')
        self.assertIn('session_info', resp.cookies)

    def test_session_info_non_httponly(self):
        """session_info doit être lisible par JS (non HttpOnly)."""
        resp = self._login()
        self.assertFalse(resp.cookies['session_info']['httponly'])

    def test_session_info_contenu_pharmacy_account(self):
        """session_info contient auth_type=pharmacy_account après login."""
        resp = self._login()
        raw = resp.cookies['session_info'].value
        data = json.loads(raw)
        self.assertEqual(data['auth_type'], 'pharmacy_account')
        self.assertIsNone(data['collaborator_id'])

    def test_refresh_token_cookie_samesite_strict(self):
        """refresh_token a l'attribut SameSite=Strict."""
        resp = self._login()
        self.assertEqual(resp.cookies['refresh_token']['samesite'], 'Strict')

    # ── Refresh sans cookie ───────────────────────────────────────────────────

    def test_refresh_sans_cookie_401(self):
        """POST /api/token/refresh/ sans cookie refresh_token → 401."""
        resp = self.client.post('/api/token/refresh/', content_type='application/json')
        self.assertEqual(resp.status_code, 401)

    def test_refresh_met_a_jour_session_info(self):
        """Après refresh, session_info est renvoyé avec auth_type=pharmacy_account."""
        refresh = RefreshToken.for_user(self.pharmacy)
        self.client.cookies['refresh_token'] = str(refresh)
        resp = self.client.post('/api/token/refresh/', content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('session_info', resp.cookies)
        data = json.loads(resp.cookies['session_info'].value)
        self.assertEqual(data['auth_type'], 'pharmacy_account')

    # ── Logout ────────────────────────────────────────────────────────────────

    def test_logout_efface_les_cookies(self):
        """POST /api/auth/logout/ renvoie 204 et supprime refresh_token + session_info."""
        refresh = RefreshToken.for_user(self.pharmacy)
        self.client.cookies['refresh_token'] = str(refresh)
        resp = self.client.post('/api/auth/logout/', content_type='application/json')
        self.assertEqual(resp.status_code, 204)
        # Django marque la suppression en posant Max-Age=0 ou une date expirée
        self.assertEqual(resp.cookies['refresh_token']['max-age'], 0)

    def test_logout_blackliste_refresh_token(self):
        """Après logout, le même refresh token ne peut plus générer un access token."""
        refresh = RefreshToken.for_user(self.pharmacy)
        token_str = str(refresh)
        self.client.cookies['refresh_token'] = token_str
        self.client.post('/api/auth/logout/', content_type='application/json')
        # Re-tenter le refresh avec le token blacklisté
        self.client.cookies['refresh_token'] = token_str
        resp = self.client.post('/api/token/refresh/', content_type='application/json')
        self.assertEqual(resp.status_code, 401)

    def test_logout_sans_cookie_204_gracieux(self):
        """Logout sans cookie → 204 (pas d'erreur)."""
        resp = self.client.post('/api/auth/logout/', content_type='application/json')
        self.assertEqual(resp.status_code, 204)

    # ── Collab logout ─────────────────────────────────────────────────────────

    def test_collab_logout_restaure_session_pharmacie(self):
        """POST /api/auth/collab-logout/ repose session_info avec auth_type=pharmacy_account."""
        resp = self.client.post('/api/auth/collab-logout/', content_type='application/json')
        self.assertEqual(resp.status_code, 204)
        self.assertIn('session_info', resp.cookies)
        data = json.loads(resp.cookies['session_info'].value)
        self.assertEqual(data['auth_type'], 'pharmacy_account')
        self.assertIsNone(data['collaborator_id'])

    def test_collab_login_session_info_contient_collaborateur(self):
        """Login PIN collaborateur → session_info contient collaborator_id et auth_type=collaborator."""
        from apps.team.models import Collaborator
        collab = Collaborator.objects.create(
            pharmacy=self.pharmacy,
            first_name='Alice',
            last_name='Collab',
            role=Collaborator.Role.PREPARATEUR,
            color='#aabbcc',
            weekly_hours=35,
        )
        collab.set_pin('1234')
        collab.save()

        client = APIClient()
        refresh = RefreshToken.for_user(self.pharmacy)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        resp = client.post('/api/team/login/', {
            'collaborator_id': collab.id,
            'pin_code': '1234',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('session_info', resp.cookies)
        data = json.loads(resp.cookies['session_info'].value)
        self.assertEqual(data['auth_type'], 'collaborator')
        self.assertEqual(data['collaborator_id'], collab.id)


# ── Vérification email ────────────────────────────────────────────────────────

class TestEmailVerification(TestCase):
    """
    Tests sur le flux complet de vérification email :
    - RegisterView déclenche la task Celery d'envoi
    - VerifyEmailView valide le token et marque email_verified=True
    - Token expiré → 400
    - Token invalide → 400
    - Renvoi d'email (resend) génère un nouveau token
    """

    def setUp(self):
        self.client = APIClient()

    @patch('apps.core.tasks.send_verification_email_task')
    def test_register_declenche_envoi_email(self, mock_task):
        """À l'inscription, la task Celery est appelée avec le bon email."""
        resp = self.client.post('/api/auth/register/', {
            'email': 'test_verif@officine.fr',
            'password': 'motdepasse123',
            'password_confirm': 'motdepasse123',
        }, format='json')

        self.assertEqual(resp.status_code, 201)
        # La task doit avoir été déclenchée une seule fois
        mock_task.delay.assert_called_once()
        call_args = mock_task.delay.call_args[0]
        self.assertEqual(call_args[0], 'test_verif@officine.fr')
        # Le token transmis doit être un UUID valide
        uuid.UUID(call_args[1])

    @patch('apps.core.tasks.send_verification_email_task')
    def test_register_cree_token_sur_pharmacy(self, mock_task):
        """À l'inscription, email_verification_token et email_verified=False sont bien enregistrés."""
        self.client.post('/api/auth/register/', {
            'email': 'token_check@officine.fr',
            'password': 'motdepasse123',
            'password_confirm': 'motdepasse123',
        }, format='json')

        pharmacy = Pharmacy.objects.get(email='token_check@officine.fr')
        self.assertIsNotNone(pharmacy.email_verification_token)
        self.assertIsNotNone(pharmacy.email_verification_expires)
        self.assertFalse(pharmacy.email_verified)

    @patch('apps.core.tasks.send_verification_email_task')
    def test_verify_email_token_valide(self, mock_task):
        """Un token valide marque email_verified=True et efface le token."""
        pharmacy = Pharmacy.objects.create_user(
            email='valid_token@officine.fr',
            password='secret123',
            nom_officine='Officine',
        )
        token = uuid.uuid4()
        pharmacy.email_verification_token = token
        pharmacy.email_verification_expires = timezone.now() + timezone.timedelta(hours=24)
        pharmacy.save(update_fields=['email_verification_token', 'email_verification_expires'])

        resp = self.client.post('/api/auth/verify-email/', {'token': str(token)}, format='json')

        self.assertEqual(resp.status_code, 200)
        pharmacy.refresh_from_db()
        self.assertTrue(pharmacy.email_verified)
        self.assertIsNone(pharmacy.email_verification_token)

    @patch('apps.core.tasks.send_verification_email_task')
    def test_verify_email_token_expire(self, mock_task):
        """Un token expiré (> 24h) retourne 400."""
        pharmacy = Pharmacy.objects.create_user(
            email='expired_token@officine.fr',
            password='secret123',
            nom_officine='Officine',
        )
        token = uuid.uuid4()
        pharmacy.email_verification_token = token
        pharmacy.email_verification_expires = timezone.now() - timezone.timedelta(hours=1)
        pharmacy.save(update_fields=['email_verification_token', 'email_verification_expires'])

        resp = self.client.post('/api/auth/verify-email/', {'token': str(token)}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('expiré', resp.data['detail'])
        pharmacy.refresh_from_db()
        self.assertFalse(pharmacy.email_verified)

    def test_verify_email_token_inconnu(self):
        """Un token inexistant retourne 400."""
        resp = self.client.post('/api/auth/verify-email/', {
            'token': str(uuid.uuid4())
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_verify_email_token_malforme(self):
        """Un token non-UUID retourne 400."""
        resp = self.client.post('/api/auth/verify-email/', {
            'token': 'pas-un-uuid'
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch('apps.core.tasks.send_verification_email_task')
    def test_resend_verification_genere_nouveau_token(self, mock_task):
        """resend-verification génère un nouveau token et déclenche la task."""
        pharmacy = Pharmacy.objects.create_user(
            email='resend@officine.fr',
            password='secret123',
            nom_officine='Officine',
        )
        old_token = uuid.uuid4()
        pharmacy.email_verification_token = old_token
        pharmacy.email_verification_expires = timezone.now() + timezone.timedelta(hours=24)
        pharmacy.save(update_fields=['email_verification_token', 'email_verification_expires'])

        refresh = RefreshToken.for_user(pharmacy)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        resp = self.client.post('/api/auth/resend-verification/', format='json')

        self.assertEqual(resp.status_code, 200)
        pharmacy.refresh_from_db()
        # Nouveau token différent de l'ancien
        self.assertNotEqual(pharmacy.email_verification_token, old_token)
        mock_task.delay.assert_called_once()

    @patch('apps.core.tasks.send_verification_email_task')
    def test_resend_verification_deja_verifie(self, mock_task):
        """resend-verification retourne 200 sans envoyer si déjà vérifié."""
        pharmacy = Pharmacy.objects.create_user(
            email='already_verified@officine.fr',
            password='secret123',
            nom_officine='Officine',
            email_verified=True,
        )
        refresh = RefreshToken.for_user(pharmacy)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        resp = self.client.post('/api/auth/resend-verification/', format='json')

        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_not_called()


# ── Changement email ──────────────────────────────────────────────────────────

class TestEmailChange(TestCase):
    """
    Tests sur le flux complet de changement d'email :
    - Demande stocke pending_email et déclenche la task Celery
    - Mauvais mot de passe → 400
    - Email déjà utilisé → 400
    - Token valide → email basculé, pending_email effacé
    - Token expiré → 400, ancien email conservé
    - Token invalide → 400
    - Annulation efface pending_email
    - Sans auth → 401
    """

    def setUp(self):
        self.client = APIClient()
        self.pharmacy = Pharmacy.objects.create_user(
            email='titulaire@officine.fr',
            password='motdepasse123',
            nom_officine='Officine Test',
        )
        refresh = RefreshToken.for_user(self.pharmacy)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    @patch('apps.core.tasks.send_email_change_task')
    def test_demande_stocke_pending_email_et_envoie(self, mock_task):
        """Demande valide : pending_email enregistré, token généré, task déclenchée."""
        resp = self.client.post('/api/account/change-email/', {
            'new_email': 'nouveau@officine.fr',
            'password': 'motdepasse123',
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.pharmacy.refresh_from_db()
        self.assertEqual(self.pharmacy.pending_email, 'nouveau@officine.fr')
        self.assertIsNotNone(self.pharmacy.email_verification_token)
        # Email actuel inchangé
        self.assertEqual(self.pharmacy.email, 'titulaire@officine.fr')
        mock_task.delay.assert_called_once()
        args = mock_task.delay.call_args[0]
        self.assertEqual(args[0], 'titulaire@officine.fr')  # old_email
        self.assertEqual(args[1], 'nouveau@officine.fr')    # new_email

    @patch('apps.core.tasks.send_email_change_task')
    def test_mauvais_mot_de_passe_400(self, mock_task):
        """Mauvais mot de passe → 400, aucun email envoyé."""
        resp = self.client.post('/api/account/change-email/', {
            'new_email': 'nouveau@officine.fr',
            'password': 'mauvais',
        }, format='json')

        self.assertEqual(resp.status_code, 400)
        mock_task.delay.assert_not_called()
        self.pharmacy.refresh_from_db()
        self.assertFalse(self.pharmacy.pending_email)  # None ou '' selon l'état initial

    @patch('apps.core.tasks.send_email_change_task')
    def test_email_deja_utilise_400(self, mock_task):
        """Email déjà pris par une autre pharmacie → 400."""
        Pharmacy.objects.create_user(
            email='pris@officine.fr',
            password='secret',
            nom_officine='Autre',
        )
        resp = self.client.post('/api/account/change-email/', {
            'new_email': 'pris@officine.fr',
            'password': 'motdepasse123',
        }, format='json')

        self.assertEqual(resp.status_code, 400)
        mock_task.delay.assert_not_called()

    @patch('apps.core.tasks.send_email_change_task')
    def test_meme_email_400(self, mock_task):
        """Même email que l'actuel → 400."""
        resp = self.client.post('/api/account/change-email/', {
            'new_email': 'titulaire@officine.fr',
            'password': 'motdepasse123',
        }, format='json')

        self.assertEqual(resp.status_code, 400)
        mock_task.delay.assert_not_called()

    def test_confirm_token_valide_bascule_email(self):
        """Token valide → email basculé, pending_email effacé, email_verified=True."""
        token = uuid.uuid4()
        self.pharmacy.pending_email = 'nouveau@officine.fr'
        self.pharmacy.email_verification_token = token
        self.pharmacy.email_verification_expires = timezone.now() + timezone.timedelta(hours=24)
        self.pharmacy.save(update_fields=['pending_email', 'email_verification_token', 'email_verification_expires'])

        # Accessible sans auth (lien depuis email)
        anon_client = APIClient()
        resp = anon_client.post('/api/account/confirm-email-change/', {'token': str(token)}, format='json')

        self.assertEqual(resp.status_code, 200)
        self.pharmacy.refresh_from_db()
        self.assertEqual(self.pharmacy.email, 'nouveau@officine.fr')
        self.assertEqual(self.pharmacy.pending_email, '')
        self.assertIsNone(self.pharmacy.email_verification_token)
        self.assertTrue(self.pharmacy.email_verified)

    def test_confirm_token_expire_400_conserve_ancien_email(self):
        """Token expiré → 400, ancien email conservé, pending_email nettoyé."""
        token = uuid.uuid4()
        self.pharmacy.pending_email = 'nouveau@officine.fr'
        self.pharmacy.email_verification_token = token
        self.pharmacy.email_verification_expires = timezone.now() - timezone.timedelta(hours=1)
        self.pharmacy.save(update_fields=['pending_email', 'email_verification_token', 'email_verification_expires'])

        anon_client = APIClient()
        resp = anon_client.post('/api/account/confirm-email-change/', {'token': str(token)}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.pharmacy.refresh_from_db()
        self.assertEqual(self.pharmacy.email, 'titulaire@officine.fr')
        self.assertEqual(self.pharmacy.pending_email, '')

    def test_confirm_token_inconnu_400(self):
        """Token inexistant → 400."""
        anon_client = APIClient()
        resp = anon_client.post('/api/account/confirm-email-change/', {
            'token': str(uuid.uuid4())
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_confirm_token_malforme_400(self):
        """Token non-UUID → 400."""
        anon_client = APIClient()
        resp = anon_client.post('/api/account/confirm-email-change/', {
            'token': 'pas-un-uuid'
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch('apps.core.tasks.send_email_change_task')
    def test_annulation_efface_pending_email(self, mock_task):
        """Annulation d'une demande en cours efface pending_email."""
        self.pharmacy.pending_email = 'nouveau@officine.fr'
        self.pharmacy.email_verification_token = uuid.uuid4()
        self.pharmacy.email_verification_expires = timezone.now() + timezone.timedelta(hours=24)
        self.pharmacy.save(update_fields=['pending_email', 'email_verification_token', 'email_verification_expires'])

        resp = self.client.post('/api/account/cancel-email-change/', format='json')

        self.assertEqual(resp.status_code, 200)
        self.pharmacy.refresh_from_db()
        self.assertEqual(self.pharmacy.pending_email, '')
        self.assertIsNone(self.pharmacy.email_verification_token)

    def test_annulation_sans_demande_400(self):
        """Annulation sans pending_email → 400."""
        resp = self.client.post('/api/account/cancel-email-change/', format='json')
        self.assertEqual(resp.status_code, 400)

    def test_demande_sans_auth_401(self):
        """Sans token JWT → 401."""
        anon_client = APIClient()
        resp = anon_client.post('/api/account/change-email/', {
            'new_email': 'test@test.fr',
            'password': 'motdepasse123',
        }, format='json')
        self.assertEqual(resp.status_code, 401)
