"""Session, revocation, and login-throttling helpers for browser authentication."""

import hashlib

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication


class StrictCsrfSessionAuthentication(SessionAuthentication):
    """Enforce CSRF for every unsafe API request, including anonymous endpoints."""

    def authenticate(self, request):
        self.enforce_csrf(request)
        return super().authenticate(request)

    def authenticate_header(self, request):
        """Return 401 (not DRF's ambiguous 403) when a session is absent."""
        return "Session"


def client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if settings.TRUST_X_FORWARDED_FOR and forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _key(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _login_keys(request, email):
    normalized_email = str(email or "").strip().casefold()
    return (
        f"security:login:ip:{_key(client_ip(request))}",
        f"security:login:email:{_key(normalized_email)}",
    )


def login_is_limited(request, email):
    return any(cache.get(key, 0) >= settings.LOGIN_MAX_ATTEMPTS for key in _login_keys(request, email))


def record_failed_login(request, email):
    for key in _login_keys(request, email):
        if cache.add(key, 1, timeout=settings.LOGIN_LOCKOUT_SECONDS):
            continue
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=settings.LOGIN_LOCKOUT_SECONDS)


def clear_failed_logins(request, email):
    cache.delete_many(_login_keys(request, email))


def _password_reset_keys(request, email):
    normalized_email = str(email or "").strip().casefold()
    return (
        f"security:password-reset:ip:{_key(client_ip(request))}",
        f"security:password-reset:email:{_key(normalized_email)}",
    )


def password_reset_is_limited(request, email):
    return any(
        cache.get(key, 0) >= settings.PASSWORD_RESET_MAX_ATTEMPTS
        for key in _password_reset_keys(request, email)
    )


def record_password_reset_request(request, email):
    for key in _password_reset_keys(request, email):
        if cache.add(key, 1, timeout=settings.PASSWORD_RESET_LOCKOUT_SECONDS):
            continue
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=settings.PASSWORD_RESET_LOCKOUT_SECONDS)


def establish_session(request, user):
    """Called after django.contrib.auth.login() rotates the session identifier."""
    request.session["security_epoch"] = user.session_epoch
    request.session["security_issued_at"] = timezone.now().timestamp()


def revoke_user_sessions(user):
    """Invalidates every active server-side session on its next request."""
    user.session_epoch += 1
    user.save(update_fields=["session_epoch"])
