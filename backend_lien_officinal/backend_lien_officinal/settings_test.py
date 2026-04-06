from .settings import *

# Force DEBUG=True en test pour désactiver le catch-all SPA et les redirects HTTPS
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Cache factice pour désactiver le throttling en test
# (les PK SQLite se réinitialisent entre les TestCase → collision des clés de throttle)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}
