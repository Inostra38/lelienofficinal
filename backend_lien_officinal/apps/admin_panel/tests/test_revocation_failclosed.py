"""S21 — la révocation des tokens admin doit être fail-CLOSED.

Le cache `default` est résilient (fail-open) : sur un hoquet Redis, .get() rend
None au lieu de lever. Utilisé pour la blacklist admin, ça ferait accepter un
token révoqué pendant une panne Redis. La blacklist vit donc dans un cache dédié
`admin_revocation` (Redis natif), et is_jti_revoked refuse le token si Redis est
injoignable.
"""
from unittest.mock import patch

from django.core.cache import caches
from django.test import SimpleTestCase

from apps.admin_panel.authentication import is_jti_revoked


class TestJtiRevocationFailClosed(SimpleTestCase):
    def setUp(self):
        caches['admin_revocation'].clear()

    def test_jti_absent_non_revoque(self):
        self.assertFalse(is_jti_revoked('jti-inconnu'))

    def test_jti_blackliste_revoque(self):
        caches['admin_revocation'].set('admin_blacklist_abc123', True, timeout=60)
        self.assertTrue(is_jti_revoked('abc123'))

    def test_jti_vide_non_revoque(self):
        self.assertFalse(is_jti_revoked(None))
        self.assertFalse(is_jti_revoked(''))

    def test_redis_injoignable_refuse_le_token(self):
        # Le cœur de S21 : si le cache lève (Redis muet), on ne peut pas prouver
        # que le token n'est PAS révoqué → on refuse (fail-closed).
        with patch.object(
            caches['admin_revocation'], 'get',
            side_effect=Exception('Error 113: No route to host'),
        ):
            self.assertTrue(is_jti_revoked('un-jti-quelconque'))
