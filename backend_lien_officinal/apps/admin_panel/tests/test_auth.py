"""
Tests apps/admin_panel — authentification admin (login, TOTP, IP whitelist).
"""

from unittest.mock import patch

import pyotp
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.admin_panel.models import AdminUser
from apps.admin_panel.crypto import encrypt_totp_secret
from apps.admin_panel.views import _issue_session_token


def _make_admin(email='admin@lienofficinal.fr', password='AdminPass1!', totp_secret=''):
    admin = AdminUser.objects.create_admin(
        email=email,
        password=password,
        full_name='Test Admin',
    )
    if totp_secret:
        admin.totp_secret = encrypt_totp_secret(totp_secret)
        admin.save(update_fields=['totp_secret'])
    return admin


# ── /api/admin/auth/login/ ─────────────────────────────────────────────────

@override_settings(ADMIN_ALLOWED_IPS='127.0.0.1')
class TestAdminLogin(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin = _make_admin()
        self.url = '/api/admin/auth/login/'

    def test_login_wrong_password_401(self):
        with patch('apps.admin_panel.views.time.sleep'):  # accélère le test
            resp = self.client.post(self.url, {
                'email': 'admin@lienofficinal.fr',
                'password': 'wrong',
            }, format='json', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(resp.status_code, 401)

    def test_login_correct_returns_session_token(self):
        resp = self.client.post(self.url, {
            'email': 'admin@lienofficinal.fr',
            'password': 'AdminPass1!',
        }, format='json', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['step'], 'totp_required')
        self.assertIn('session_token', resp.data)
        self.assertTrue(len(resp.data['session_token']) > 20)

    def test_login_unknown_email_401(self):
        with patch('apps.admin_panel.views.time.sleep'):
            resp = self.client.post(self.url, {
                'email': 'nobody@lienofficinal.fr',
                'password': 'AdminPass1!',
            }, format='json', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(resp.status_code, 401)


# ── /api/admin/auth/totp-verify/ ──────────────────────────────────────────

@override_settings(ADMIN_ALLOWED_IPS='127.0.0.1')
class TestAdminTotpVerify(TestCase):
    TOTP_SECRET = 'JBSWY3DPEHPK3PXP'

    def setUp(self):
        self.client = APIClient()
        self.admin = _make_admin(totp_secret=self.TOTP_SECRET)
        self.url = '/api/admin/auth/totp-verify/'
        self.session_token = _issue_session_token(self.admin.pk)

    def test_totp_verify_wrong_code_401(self):
        # Patch pyotp.TOTP.verify au niveau de la classe (s'applique à toutes les instances)
        with patch.object(pyotp.TOTP, 'verify', return_value=False):
            resp = self.client.post(self.url, {
                'session_token': self.session_token,
                'totp_code': '000000',
            }, format='json', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(resp.status_code, 401)

    def test_totp_verify_correct_returns_access_token_and_cookie(self):
        # Génère un vrai code TOTP depuis le secret connu — test le flux complet
        code = pyotp.TOTP(self.TOTP_SECRET).now()
        resp = self.client.post(self.url, {
            'session_token': self.session_token,
            'totp_code': code,
        }, format='json', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access_token', resp.data)
        self.assertTrue(len(resp.data['access_token']) > 20)
        self.assertIn('admin_refresh_token', resp.cookies)
        cookie = resp.cookies['admin_refresh_token']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Strict')

    def test_totp_verify_invalid_session_token_401(self):
        resp = self.client.post(self.url, {
            'session_token': 'invalid.token.here',
            'totp_code': '123456',
        }, format='json', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(resp.status_code, 401)


# ── IP whitelist (AdminIPWhitelistMiddleware) ──────────────────────────────

class TestAdminIPWhitelist(TestCase):

    def setUp(self):
        self.client = APIClient()
        _make_admin()

    @override_settings(ADMIN_ALLOWED_IPS='10.0.0.1')
    def test_ip_blocked_returns_403(self):
        resp = self.client.post('/api/admin/auth/login/', {
            'email': 'admin@lienofficinal.fr',
            'password': 'AdminPass1!',
        }, format='json', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(resp.status_code, 403)

    @override_settings(ADMIN_ALLOWED_IPS='127.0.0.1')
    def test_ip_allowed_passes_middleware(self):
        with patch('apps.admin_panel.views.time.sleep'):
            resp = self.client.post('/api/admin/auth/login/', {
                'email': 'admin@lienofficinal.fr',
                'password': 'wrong',
            }, format='json', REMOTE_ADDR='127.0.0.1')
        # Le middleware laisse passer → la vue répond (401 et non 403)
        self.assertEqual(resp.status_code, 401)

    @override_settings(ADMIN_ALLOWED_IPS='127.0.0.1', ADMIN_TRUSTED_PROXY_COUNT=1)
    def test_ip_from_x_forwarded_for(self):
        """L'IP est lue depuis X-Forwarded-For, position anti-spoof (E2).

        Avec 1 proxy de confiance (Scalingo), l'IP fiable est la DERNIÈRE de
        X-Forwarded-For (ajoutée par notre infra) ; les entrées de gauche sont
        contrôlables par le client. La vraie IP cliente (127.0.0.1) est donc en
        fin de chaîne ; '10.0.0.99' à gauche simule une tentative de spoof.
        """
        resp = self.client.post('/api/admin/auth/login/', {
            'email': 'admin@lienofficinal.fr',
            'password': 'AdminPass1!',
        }, format='json',
           REMOTE_ADDR='10.0.0.99',
           HTTP_X_FORWARDED_FOR='10.0.0.99, 127.0.0.1')
        # 127.0.0.1 (dernière entrée = fiable) est whitelistée → pas de 403
        self.assertNotEqual(resp.status_code, 403)
