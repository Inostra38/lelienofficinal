"""Tests du backend de cache résilient (fail-open sur panne Redis)."""
import importlib
import os
from unittest.mock import patch

from django.test import SimpleTestCase
from redis.exceptions import TimeoutError as RedisTimeoutError

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

    @patch(REDIS_GET, side_effect=RedisTimeoutError('Timeout reading from socket'))
    def test_get_fails_open_on_socket_timeout(self, _m):
        # Le cas réel de l'incident : socket morte. Sans OPTIONS.socket_timeout,
        # redis-py ne lèverait pas ceci — il attendrait indéfiniment.
        self.assertEqual(self.cache.get('throttle_login_1.2.3.4', []), [])

    @patch(REDIS_SET, side_effect=RedisTimeoutError('Timeout writing to socket'))
    def test_set_fails_open_on_socket_timeout(self, _m):
        self.assertIs(self.cache.set('k', 'v'), False)


class RedisTimeoutSettingsTests(SimpleTestCase):
    """Les timeouts sont porteurs : sans eux, une socket Redis morte fige le
    conteneur ASGI entier (toutes les vues sync partagent un thread unique).

    On vise le module de settings de prod, car settings_test remplace CACHES
    par un DummyCache.
    """

    @staticmethod
    def _reload(module, **env):
        # reload() ré-exécute settings.py : neutraliser sentry_sdk.init, qui
        # sinon se ré-initialiserait depuis un test dès qu'un DSN est présent.
        with patch.dict(os.environ, env), patch('sentry_sdk.init'):
            importlib.reload(module)

    def test_cache_declares_socket_timeouts(self):
        from backend_lien_officinal import settings as prod_settings

        options = prod_settings.CACHES['default']['OPTIONS']
        self.assertGreater(options['socket_connect_timeout'], 0)
        self.assertGreater(options['socket_timeout'], 0)

    def test_channel_layer_socket_timeout_exceeds_brpop_timeout(self):
        from channels_redis.core import RedisChannelLayer
        from backend_lien_officinal import settings as prod_settings

        # CHANNEL_LAYERS ne prend la branche Redis que si REDIS_URL est défini.
        self.addCleanup(self._reload, prod_settings)
        self._reload(prod_settings, REDIS_URL='redis://localhost:6379/0')

        host = prod_settings.CHANNEL_LAYERS['default']['CONFIG']['hosts'][0]
        # Un socket_timeout <= brpop_timeout ferait lever chaque receive() WebSocket.
        self.assertGreater(host['socket_timeout'], RedisChannelLayer.brpop_timeout)
        self.assertGreater(host['socket_connect_timeout'], 0)
