from pathlib import Path
import os
import sys
from datetime import timedelta
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

load_dotenv()  # Charge les variables depuis .env

# --- SENTRY (monitoring erreurs) ---
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.2,
        send_default_pii=False,
    )

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- 1. ARCHITECTURE MODULAIRE ---
# Ajout du dossier 'apps' au chemin système pour les imports (ex: 'apps.core')
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# F2 : fail-safe — DEBUG désactivé par défaut, à activer explicitement en dev.
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

SECRET_KEY = os.environ.get('SECRET_KEY')
# C3 : interdire le démarrage avec une clé faible/par défaut, quel que soit DEBUG.
# Cette clé signe TOUS les JWT (HTTP + WebSocket) ; une valeur publique connue
# permettrait de forger des tokens arbitraires. Générer une vraie clé même en dev :
#   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
if not SECRET_KEY or SECRET_KEY.startswith('django-insecure'):
    raise Exception(
        "SECRET_KEY manquante ou non sécurisée. Définissez une clé aléatoire forte "
        "dans la variable d'environnement SECRET_KEY (≥ 50 caractères), y compris en développement."
    )

# E1 : secrets admin dédiés, INDÉPENDANTS de SECRET_KEY.
# Avant, les JWT admin étaient signés avec SECRET_KEY et les secrets TOTP
# dérivés de sha256(SECRET_KEY) : une seule fuite de SECRET_KEY permettait de
# forger des JWT admin ET de déchiffrer tous les secrets TOTP (bypass 2FA).
# En production, ces deux clés DOIVENT être définies et distinctes.
# En dev, on les dérive de façon namespacée depuis SECRET_KEY pour éviter une
# config supplémentaire, tout en conservant une séparation logique.
ADMIN_JWT_SECRET = os.environ.get('ADMIN_JWT_SECRET')
ADMIN_TOTP_KEY = os.environ.get('ADMIN_TOTP_KEY')
if not DEBUG:
    if not ADMIN_JWT_SECRET or not ADMIN_TOTP_KEY:
        raise Exception(
            "ADMIN_JWT_SECRET et ADMIN_TOTP_KEY doivent être définis (et distincts "
            "de SECRET_KEY) en production. Générer : "
            "python -c \"import secrets; print(secrets.token_urlsafe(50))\""
        )
else:
    import hashlib as _hashlib
    if not ADMIN_JWT_SECRET:
        ADMIN_JWT_SECRET = _hashlib.sha256(('admin-jwt:' + SECRET_KEY).encode()).hexdigest()
    if not ADMIN_TOTP_KEY:
        ADMIN_TOTP_KEY = _hashlib.sha256(('admin-totp:' + SECRET_KEY).encode()).hexdigest()

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# Application definition

INSTALLED_APPS = [
    'daphne',           # WebSocket ASGI — doit être en premier
    'channels',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # --- TIERCE PARTIES ---
    'django.contrib.postgres',  # Index partiels, CheckConstraints PostgreSQL
    'rest_framework',
    'rest_framework_simplejwt',                   # Authentification Token
    'rest_framework_simplejwt.token_blacklist',    # Invalidation des tokens après changement de mdp
    'corsheaders',              # Communication Angular <-> Django
    'encrypted_model_fields',   # Chiffrement au repos (messagerie)
    'storages',                 # Scaleway Object Storage (S3)

    # --- NOS APPS (Le Lien Officinal) ---
    'apps.core',           # Auth Pharmacie
    'apps.team',           # Collaborateurs & PIN
    'apps.resources',      # Liens & Catégories
    'apps.partners',       # Pubs & Labos
    'apps.messaging',      # Messagerie d'équipe
    'apps.tasks',          # Gestion des tâches
    'apps.planning',       # Planning d'équipe
    'apps.quality',        # Qualité & procédures
    'apps.admin_panel',    # Admin SaaS interne
    'apps.billing',        # Abonnements Stripe & crédits SMS
    # 'apps.notifications',  # Système de notifs (TEMPORAIREMENT DÉSACTIVÉ)
]

MIDDLEWARE = [
    # --- IP whitelist admin (EN PREMIER : bloque avant tout traitement) ---
    'apps.admin_panel.middleware.AdminIPWhitelistMiddleware',

    # --- Sécurité HTTP (HSTS, X-Content-Type-Options, etc.) ---
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    # --- CORS (après SecurityMiddleware pour que les headers sécu soient présents) ---
    'corsheaders.middleware.CorsMiddleware',

    # --- Rate limiting admin par IP (indépendant de DRF) ---
    'apps.admin_panel.middleware.AdminRateLimitMiddleware',

    # --- Guard admin (force password change + TOTP, après CORS) ---
    'apps.admin_panel.middleware.AdminAccountGuardMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.ContentSecurityPolicyMiddleware',
]

# --- Headers de sécurité HTTP ---
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

ROOT_URLCONF = 'backend_lien_officinal.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend_lien_officinal.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

# --- Base de données ---
# Priorité 1 : DATABASE_URL (Scalingo, Heroku — format postgres://user:pass@host/db)
# Priorité 2 : DB_NAME/DB_USER/… séparés (déploiement serveur dédié)
# Priorité 3 : SQLite (développement local)
if os.environ.get("DATABASE_URL"):
    import dj_database_url
    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=0)}
elif os.environ.get("DB_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "lien_officinal"),
            "USER": os.environ.get("DB_USER", "lien_user"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# --- 3. AUTHENTIFICATION PERSONNALISÉE ---
AUTH_USER_MODEL = 'core.Pharmacy'


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'fr-fr' # Français

TIME_ZONE = 'Europe/Paris' # Fuseau horaire Paris

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Build Angular inclus dans collectstatic si présent (multi-buildpack Scalingo)
_ANGULAR_DIST = BASE_DIR.parent / 'frontend-lien-officinal' / 'dist' / 'frontend-lien-officinal' / 'browser'
STATICFILES_DIRS = [_ANGULAR_DIST] if _ANGULAR_DIST.is_dir() else []

# WhiteNoise sert les fichiers Angular directement à la racine /
# (main-XXX.js, styles-XXX.css, etc. accessibles sans /static/)
WHITENOISE_ROOT = str(STATIC_ROOT)

# --- Scaleway Object Storage (S3-compatible) ---
SCW_ACCESS_KEY = os.environ.get('SCW_ACCESS_KEY')
SCW_SECRET_KEY = os.environ.get('SCW_SECRET_KEY')
SCW_BUCKET_NAME = os.environ.get('SCW_BUCKET_NAME', 'lienofficinal-media')
SCW_REGION = os.environ.get('SCW_REGION', 'fr-par')

if SCW_ACCESS_KEY and SCW_SECRET_KEY:
    # Production : Scaleway S3
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
    AWS_ACCESS_KEY_ID = SCW_ACCESS_KEY
    AWS_SECRET_ACCESS_KEY = SCW_SECRET_KEY
    AWS_STORAGE_BUCKET_NAME = SCW_BUCKET_NAME
    AWS_S3_REGION_NAME = SCW_REGION
    AWS_S3_ENDPOINT_URL = f'https://s3.{SCW_REGION}.scw.cloud'
    AWS_QUERYSTRING_AUTH = True          # signed URLs (privé)
    AWS_QUERYSTRING_EXPIRE = 3600       # URLs valides 1h
    AWS_DEFAULT_ACL = 'private'
    AWS_S3_FILE_OVERWRITE = False
    MEDIA_URL = f'https://{SCW_BUCKET_NAME}.s3.{SCW_REGION}.scw.cloud/'
else:
    # Dev local : stockage fichiers classique
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================
# CONFIGURATION API & SÉCURITÉ (ANGULAR)
# ==============================================================

# --- CORS : Qui a le droit de LIRE les données ? ---
# Autorise Angular à faire des requêtes GET
CORS_ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]
# En production : CORS_ALLOWED_ORIGINS=https://lelienofficinal.fr,https://www.lelienofficinal.fr
if _extra_cors := os.environ.get('CORS_ALLOWED_ORIGINS', ''):
    CORS_ALLOWED_ORIGINS += [o.strip() for o in _extra_cors.split(',') if o.strip()]

# Nécessaire pour que le cookie HttpOnly admin_refresh_token soit envoyé/reçu
CORS_ALLOW_CREDENTIALS = True

# Headers personnalisés autorisés (inclut X-Collaborator-Id pour la messagerie)
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-collaborator-id',
]

# --- CSRF : Qui a le droit d'ÉCRIRE (POST/PUT/DELETE) ? ---
# CRUCIAL : Autorise Angular à faire des POST sans être bloqué par la sécurité CSRF
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]

# --- REST FRAMEWORK : Config de l'API ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # ⚠️ CRITIQUE POUR ÉVITER LE BUG CSRF :
        # On active UNIQUEMENT le JWT.
        # On NE MET PAS 'SessionAuthentication' ici pour éviter que Django
        # ne vérifie le cookie de l'admin quand on utilise l'API.
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        # Par défaut, il faut être connecté pour accéder à l'API
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'user': '1000/day',       # limite globale par défaut
        'login': '10/min',        # E3 : login pharmacie /api/token/ (anti brute-force par IP)
        'register': '5/hour',     # création de compte (anti-spam)
        'messaging': '30/minute', # envoi de messages (REST fallback)
        'sms_send': '200/hour',             # envoi SMS par pharmacie
        'sms_send_collaborator': '50/hour', # envoi SMS par collaborateur
        'admin_login': '5/hour',            # tentatives login admin
        'admin_totp': '10/hour',            # tentatives TOTP admin
    },
}

# --- JWT : Durée de vie du token ---
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Durée de vie réduite pour les tokens collaborateurs (session PIN)
COLLABORATOR_TOKEN_LIFETIME = timedelta(minutes=30)


# --- CHIFFREMENT AU REPOS (Messagerie) — E5 Phase 1 ---
# Clé(s) de chiffrement des champs sensibles (messagerie = données de santé).
# Support d'une LISTE de clés séparées par des virgules pour la ROTATION :
# la 1re clé chiffre, toutes déchiffrent (MultiFernet). Pour roter :
#   1. mettre "nouvelle_clé,ancienne_clé" dans FIELD_ENCRYPTION_KEY
#   2. lancer `manage.py reencrypt_messaging` (re-chiffre tout avec la nouvelle)
#   3. retirer l'ancienne clé de la variable
# La clé doit être fournie via l'environnement / un KMS — jamais en dur ni vide.
FIELD_ENCRYPTION_KEY = [
    k.strip() for k in os.environ.get('FIELD_ENCRYPTION_KEY', '').split(',') if k.strip()
]
if not FIELD_ENCRYPTION_KEY:
    raise Exception(
        "FIELD_ENCRYPTION_KEY manquante : définissez au moins une clé Fernet "
        "(via l'environnement / un KMS). Générer : "
        "python manage.py generate_encryption_key"
    )

# --- WEBSOCKET / DJANGO CHANNELS ---
ASGI_APPLICATION = "backend_lien_officinal.asgi.application"

# Scalingo fournit SCALINGO_REDIS_URL, en local c'est REDIS_URL
_REDIS_URL = os.environ.get('SCALINGO_REDIS_URL') or os.environ.get('REDIS_URL')

if _REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [_REDIS_URL],
            },
        }
    }
else:
    # Développement local uniquement
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }

# --- Admin Panel ---
ADMIN_ALLOWED_IPS = os.environ.get('ADMIN_ALLOWED_IPS', '127.0.0.1')

# E2 : nombre de proxys de confiance devant l'app (qui ajoutent X-Forwarded-For).
# L'IP client réelle est lue depuis la DROITE de la chaîne XFF en sautant ce
# nombre d'entrées, pour qu'un client ne puisse pas usurper son IP en forgeant
# le header. Scalingo place un routeur edge unique → 1 par défaut.
ADMIN_TRUSTED_PROXY_COUNT = int(os.environ.get('ADMIN_TRUSTED_PROXY_COUNT', '1'))

# --- API Claude (Anthropic) ---
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# --- SMS Partner ---
SMSPARTNER_API_KEY = os.environ.get('SMSPARTNER_API_KEY', '')
SMSPARTNER_SENDER = os.environ.get('SMSPARTNER_SENDER', 'LienOfficin')

# Clé secrète pour valider les webhooks SMS Partner (accusés de réception)
SMS_WEBHOOK_SECRET = os.environ.get('SMS_WEBHOOK_SECRET', '')

# --- Mailgun ---
MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY', '')
MAILGUN_DOMAIN = os.environ.get('MAILGUN_DOMAIN', 'mg.lienofficinal.fr')
FRONTEND_BASE_URL = os.environ.get('FRONTEND_BASE_URL', 'http://localhost:4200')
ADMIN_NOTIFICATION_EMAIL = os.environ.get('ADMIN_NOTIFICATION_EMAIL', 'admin@lienofficinal.fr')

# --- Stripe (abonnements + packs SMS) ---
STRIPE_SECRET_KEY      = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET  = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRICE_SMALL     = os.environ.get('STRIPE_PRICE_SMALL', '')
STRIPE_PRICE_LARGE     = os.environ.get('STRIPE_PRICE_LARGE', '')

# --- CACHE (Redis) ---
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": _REDIS_URL or 'redis://localhost:6379/1',
    }
}

# --- CELERY ---
CELERY_BROKER_URL = _REDIS_URL or 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = _REDIS_URL or 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Paris'

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    'sms-cleanup-old-logs': {
        'task': 'sms.cleanup_old_sms_logs',
        'schedule': crontab(hour=2, minute=0),  # chaque nuit à 2h00
    },
    'billing-check-plan-upgrades-nightly': {
        'task': 'apps.billing.tasks.check_plan_upgrades',
        'schedule': crontab(hour=2, minute=0),  # chaque nuit à 2h00
    },
}

# --- LOGGING ---
_LOG_DIR = BASE_DIR / 'logs'
_LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
        "admin_audit": {
            "format": "[{asctime}] {levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "admin_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(_LOG_DIR / "admin_audit.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5 Mo
            "backupCount": 10,
            "formatter": "admin_audit",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "WARNING"),
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "apps.admin_panel": {
            "handlers": ["console", "admin_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}