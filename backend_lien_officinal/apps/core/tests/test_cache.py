"""Tests du backend de cache résilient (fail-open sur panne Redis)."""
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.cache import ResilientRedisCache

REDIS_GET = 'django.core.cache.backends.redis.RedisCache.get'
REDIS_SET = 'django.core.cache.backends.redis.RedisCache.set'


class ResilientRedisCacheTests(SimpleTestCase):
    def setUp(self):
        self.cache = ResilientRedisCache('redis://localhost:6379/1', {})

    @patch(REDIS_GET, side_effect=Exception('Error 113: No route to host'))
    def test_get_fails_open_returns_default(self, _m):
        # Comportement clé : le throttle DRF fait cache.get(key, []) → doit
        # renvoyer [] (et donc autoriser la requête) au lieu de lever une 500.
        self.assertEqual(self.cache.get('throttle_login_1.2.3.4', []), [])

    @patch(REDIS_SET, side_effect=Exception('Error 113: No route to host'))
    def test_set_fails_open_does_not_raise(self, _m):
        # Ne doit pas lever ; renvoie False (écriture non effectuée).
        self.assertIs(self.cache.set('k', 'v'), False)

    @patch(REDIS_GET, return_value=['x'])
    def test_get_passthrough_when_redis_ok(self, _m):
        # Quand Redis répond, on relaie normalement.
        self.assertEqual(self.cache.get('k', []), ['x'])
