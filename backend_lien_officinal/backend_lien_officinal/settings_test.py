from .settings import *

# Force DEBUG=True en test pour désactiver le catch-all SPA et les redirects HTTPS
DEBUG = True

# settings.py calcule les réglages de sécurité À L'IMPORT, depuis la variable
# d'environnement DEBUG. Les redéfinir ici après coup ne les recalcule pas :
# en CI, où DEBUG n'est pas exporté, SECURE_SSL_REDIRECT restait à True et
# TOUTE requête de test partait en 301 — d'où des centaines d'échecs du type
# « 301 != 200 ». Invisible en local, où .env fixe DEBUG=True.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

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
    },
    # Révocation admin : cache local fonctionnel (pas Dummy) pour que la
    # blacklist opère réellement dans les tests. En prod c'est du Redis natif.
    'admin_revocation': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'admin-revocation-test',
    },
}
