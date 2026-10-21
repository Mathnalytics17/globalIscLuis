from django.conf import settings
from django.contrib.auth import logout
from django.utils import timezone


class SessionSecurityMiddleware:
    """Rejects revoked, disabled, and over-age authenticated sessions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        session_expired = False
        if user and user.is_authenticated:
            issued_at = request.session.get("security_issued_at")
            current_epoch = request.session.get("security_epoch")
            expired = (
                not issued_at
                or timezone.now().timestamp() - float(issued_at)
                > settings.SESSION_ABSOLUTE_AGE
            )
            revoked = current_epoch != user.session_epoch
            unavailable = (
                not user.is_active
                or user.access_status
                in {user.AccessStatus.BLOCKED, user.AccessStatus.DISABLED}
            )
            if expired or revoked or unavailable:
                session_expired = True
                logout(request)
                request.session["security_reauth_required"] = True

        response = self.get_response(request)
        # Keep an expired/revoked session distinguishable from a genuine RBAC
        # denial. Some endpoint stacks can return 403 after logout; clients
        # must still send the person to sign in rather than show a misleading
        # resource/permission message.
        if session_expired:
            response.headers["X-Session-Expired"] = "1"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
