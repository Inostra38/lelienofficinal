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

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-CHANGE-ME-IN-PRODUCTION')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

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

    # --- NOS APPS (Le Lien Officinal) ---
    'apps.core',           # Auth Pharmacie
    'apps.team',           # Collaborateurs & PIN
    'apps.resources',      # Liens & Catégories
    'apps.partners',       # Pubs & Labos
    'apps.messaging',      # Messagerie d'équipe
    'apps.tasks',          # Gestion des tâches
    'apps.planning',       # Planning d'équipe
    'apps.quality',        # Qualité & procédures
    # 'apps.notifications',  # Système de notifs (TEMPORAIREMENT DÉSACTIVÉ)
]

MIDDLEWARE = [
    # --- 2. CORS (IMPÉRATIVEMENT EN PREMIER) ---
    'corsheaders.middleware.CorsMiddleware',
    
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

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

# --- PostgreSQL (production) ---
# Variables d'environnement : DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
# Si DB_NAME absent → fallback SQLite pour le développement local
if os.environ.get("DB_NAME"):
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
    # --- SQLite (fallback développement local) ---
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

STATIC_URL = 'static/'

# --- 4. GESTION DES FICHIERS MÉDIAS (Images/PDF) ---
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
        'messaging': '30/minute', # envoi de messages (REST fallback)
        'sms_send': '200/hour',             # envoi SMS par pharmacie
        'sms_send_collaborator': '50/hour', # envoi SMS par collaborateur
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

# URL de base du backend (pour les fichiers media)
BACKEND_BASE_URL = 'http://127.0.0.1:8000'

# --- CHIFFREMENT AU REPOS (Messagerie) ---
FIELD_ENCRYPTION_KEY = os.environ.get('FIELD_ENCRYPTION_KEY', '')

# --- WEBSOCKET / DJANGO CHANNELS ---
ASGI_APPLICATION = "backend_lien_officinal.asgi.application"

if os.environ.get('REDIS_URL'):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [os.environ.get('REDIS_URL')],
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

# --- API Claude (Anthropic) ---
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# --- OVH SMS ---
OVH_ENDPOINT = 'ovh-eu'
OVH_APP_KEY = os.environ.get('OVH_APP_KEY', 'DUMMY_KEY')
OVH_APP_SECRET = os.environ.get('OVH_APP_SECRET', 'DUMMY_SECRET')
OVH_CONSUMER_KEY = os.environ.get('OVH_CONSUMER_KEY', 'DUMMY_CONSUMER')
OVH_SMS_SERVICE = os.environ.get('OVH_SMS_SERVICE', 'sms-XXXX-1')

# Clé secrète pour valider les webhooks OVH (accusés de réception)
SMS_WEBHOOK_SECRET = os.environ.get('SMS_WEBHOOK_SECRET', '')

# --- CELERY ---
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Paris'

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    'sms-cleanup-old-logs': {
        'task': 'sms.cleanup_old_sms_logs',
        'schedule': crontab(hour=2, minute=0),  # chaque nuit à 2h00
    },
}

# --- LOGGING ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
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
    },
}