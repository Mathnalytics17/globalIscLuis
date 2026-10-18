import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_DIR = BASE_DIR.parent

# Docker injects its selected env_file before Django starts. When running the
# source code directly, fall back to .env only if no runtime environment has
# already been selected. This avoids .env.local silently inheriting .env.
if not os.getenv("DJANGO_ENV"):
    load_dotenv(ENV_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=None):
    value = os.getenv(name)
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


ENVIRONMENT = os.getenv("DJANGO_ENV", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"
DEBUG = env_bool("DJANGO_DEBUG", not IS_PRODUCTION)


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise ImproperlyConfigured(f"{name} is required when DJANGO_ENV=production.")
    return value


if IS_PRODUCTION:
    if DEBUG:
        raise ImproperlyConfigured("DJANGO_DEBUG must be false when DJANGO_ENV=production.")
    # Do not silently deploy a public service with development fallbacks.
    for _setting in (
        "DJANGO_ALLOWED_HOSTS", "CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS",
        "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST",
        "REDIS_URL", "EMAIL_HOST", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD",
        "DEFAULT_FROM_EMAIL",
    ):
        required_env(_setting)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is required when DJANGO_ENV=production."
        )
    SECRET_KEY = "dev-only-change-me-global-oil"

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    ["localhost", "127.0.0.1", "195.250.25.25"],
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000/")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "django_filters",
    "apps.activesTree.apps.ActivestreeConfig",
    "apps.users",
    "apps.misc",
    "apps.muestras",
    "apps.reporte",
    "apps.resultado",
    "apps.dashboard",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "backend.middleware.SessionSecurityMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"
WSGI_APPLICATION = "backend.wsgi.application"
ASGI_APPLICATION = "backend.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "apps" / "media" / "templates",
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "globaliscdb"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "1"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}


# Redis is the server-side store for authenticated sessions and login limits.
# Development gets an isolated local cache; production must provide private Redis.
REDIS_URL = os.getenv("REDIS_URL")
if IS_PRODUCTION and not REDIS_URL:
    REDIS_URL = required_env("REDIS_URL")

if REDIS_URL:
    _redis_options = {
        "CLIENT_CLASS": "django_redis.client.DefaultClient",
        "SOCKET_CONNECT_TIMEOUT": 3,
        "SOCKET_TIMEOUT": 3,
        "IGNORE_EXCEPTIONS": False,
    }
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": _redis_options,
            "KEY_PREFIX": os.getenv("CACHE_KEY_PREFIX", "globaloil"),
        },
        "sessions": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": _redis_options,
            "KEY_PREFIX": f"{os.getenv('CACHE_KEY_PREFIX', 'globaloil')}:sessions",
        },
    }
else:
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        "sessions": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    }

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "sessions"
SESSION_COOKIE_NAME = "__Host-globaloil_session" if IS_PRODUCTION else "globaloil_session"
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "1800"))
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_DOMAIN = None
SESSION_COOKIE_PATH = "/"
SESSION_ABSOLUTE_AGE = int(os.getenv("SESSION_ABSOLUTE_AGE", "28800"))
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "900"))
PASSWORD_RESET_MAX_ATTEMPTS = int(os.getenv("PASSWORD_RESET_MAX_ATTEMPTS", "3"))
PASSWORD_RESET_LOCKOUT_SECONDS = int(os.getenv("PASSWORD_RESET_LOCKOUT_SECONDS", "3600"))
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", IS_PRODUCTION)


AUTH_USER_MODEL = "users.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "backend.auth.EmailAuthBackend.EmailAuthBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "backend.api_exceptions.api_exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.users.api.session_security.StrictCsrfSessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
}

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://195.250.25.25:3000",
        "http://195.250.25.25:8000",
    ],
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "idempotency-key",
    "x-requested-with",
]
CORS_EXPOSE_HEADERS = ["content-type", "authorization"]

CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_HTTPONLY = False  # The browser reads this non-secret token for X-CSRFToken.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", CORS_ALLOWED_ORIGINS)
CSRF_FAILURE_VIEW = "backend.views.csrf_failure"


EMAIL_VERIFICATION_TOKEN_EXPIRY_DAYS = int(
    os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRY_DAYS", "3")
)
PASSWORD_RESET_TOKEN_EXPIRY_HOURS = int(
    os.getenv("PASSWORD_RESET_TOKEN_EXPIRY_HOURS", "24")
)

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))


LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "es-co")
TIME_ZONE = os.getenv("TIME_ZONE", "America/Bogota")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "apps" / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Production-safe defaults. They remain configurable for local development and
# for deployments behind a reverse proxy that terminates TLS.
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = os.getenv("X_FRAME_OPTIONS", "DENY")
SECURE_REFERRER_POLICY = os.getenv(
    "SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin"
)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", IS_PRODUCTION)
SECURE_HSTS_SECONDS = int(
    os.getenv("SECURE_HSTS_SECONDS", "31536000" if IS_PRODUCTION else "0")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", IS_PRODUCTION
)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", IS_PRODUCTION)
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if env_bool("TRUST_X_FORWARDED_PROTO", False)
    else None
)
