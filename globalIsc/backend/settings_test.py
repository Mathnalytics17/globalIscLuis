"""Pytest-only settings: never use the runtime Redis or its sessions."""

from .settings import *  # noqa: F403


CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "globaloil-test-default",
    },
    "sessions": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "globaloil-test-sessions",
    },
}
SESSION_CACHE_ALIAS = "sessions"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
