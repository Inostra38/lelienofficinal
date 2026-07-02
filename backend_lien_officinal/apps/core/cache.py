"""Backend de cache Redis « fail-open ».

Le backend Redis natif de Django (``django.core.cache.backends.redis``) **lève**
une exception si Redis est injoignable. Conséquence : un simple hoquet Redis fait
tomber tout ce qui dépend du cache — en particulier les throttles DRF, qui lèvent
alors une 500 dans ``check_throttles`` sur TOUS les endpoints throttlés (login,
inscription, promo, SMS, reset mot de passe, login admin…).

Ce backend dégrade proprement : si Redis tousse, les lectures renvoient le défaut
et les écritures sont des no-op, au lieu de mettre l'auth/l'API à terre. Le
rate-limiting est temporairement désactivé (acceptable) mais l'app reste debout.
"""
import logging

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.redis import RedisCache

logger = logging.getLogger(__name__)


class ResilientRedisCache(RedisCache):
    """RedisCache qui n'échoue jamais en dur : fail-open sur erreur Redis."""

    def get(self, key, default=None, version=None):
        try:
            return super().get(key, default, version)
        except Exception:
            logger.warning('Cache Redis indisponible (get) — fail-open', exc_info=True)
            return default

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().set(key, value, timeout, version)
        except Exception:
            logger.warning('Cache Redis indisponible (set) — fail-open', exc_info=True)
            return False

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().add(key, value, timeout, version)
        except Exception:
            return False

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().touch(key, timeout, version)
        except Exception:
            return False

    def delete(self, key, version=None):
        try:
            return super().delete(key, version)
        except Exception:
            return False

    def incr(self, key, delta=1, version=None):
        try:
            return super().incr(key, delta, version)
        except Exception:
            logger.warning('Cache Redis indisponible (incr) — fail-open', exc_info=True)
            return delta

    def get_many(self, keys, version=None):
        try:
            return super().get_many(keys, version)
        except Exception:
            logger.warning('Cache Redis indisponible (get_many) — fail-open', exc_info=True)
            return {}

    def set_many(self, data, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().set_many(data, timeout, version)
        except Exception:
            return list(data)
