"""
Tests core/views.py — Register, JWT (forgé/expiré/refresh), endpoints protégés
"""

import json
import time

from django.test import TestCase
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

    def test_register_succes_201(self):
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

    def test_register_email_domaine_normalise_minuscule(self):
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

    def test_register_set_session_info_cookie(self):
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
