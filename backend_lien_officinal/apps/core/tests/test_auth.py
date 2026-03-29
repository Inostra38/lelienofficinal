"""
Tests core/views.py — Register, JWT (forgé/expiré/refresh), endpoints protégés
"""

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
