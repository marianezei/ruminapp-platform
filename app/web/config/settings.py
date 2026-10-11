import os
import sys
from pathlib import Path

from config import telemetria

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = os.environ.get(
    "RUMINAPP_SECRET_KEY", "django-insecure-apenas-para-desenvolvimento-local"
)

DEBUG = os.environ.get("RUMINAPP_DEBUG", "1") == "1"

ALLOWED_HOSTS = os.environ.get("RUMINAPP_HOSTS", "*").split(",")


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rebanho',
]

MIDDLEWARE = [
    'config.middleware.SaudeMiddleware',
    'config.middleware.MetricasMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'rebanho.context_processors.tema_visual',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


if os.environ.get("DATABASE_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["DATABASE_HOST"],
            "PORT": os.environ.get("DATABASE_PORT", "5432"),
            "NAME": os.environ.get("DATABASE_NAME", "ruminapp"),
            "USER": os.environ.get("DATABASE_USER", "ruminapp"),
            "PASSWORD": os.environ.get("DATABASE_PASSWORD", ""),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {"connect_timeout": 3},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("RUMINAPP_BANCO", BASE_DIR / "db.sqlite3"),
        }
    }

REPRODUCAO_URL = os.environ.get("REPRODUCAO_URL", "http://localhost:8081").rstrip("/")
REPRODUCAO_TIMEOUT = float(os.environ.get("REPRODUCAO_TIMEOUT", "3"))

LOGGING_CONFIG = None
telemetria.configurar_logs()


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


LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Recife'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'painel'
LOGOUT_REDIRECT_URL = 'login'

STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
if sys.argv[1:2] == ["test"]:
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
    MIDDLEWARE.remove("whitenoise.middleware.WhiteNoiseMiddleware")

CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("RUMINAPP_ORIGENS", "").split(",") if o
]
