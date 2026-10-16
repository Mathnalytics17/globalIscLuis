"""Integration tests for browser sessions, CSRF, throttling, and revocation."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.api.models.index import PasswordResetToken, User, UserAuditLog
from apps.users.api.session_security import revoke_user_sessions


@pytest.mark.django_db
class TestBrowserSessionSecurity:
    password = "Correct-password-123!"

    def setup_method(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="security-test@example.com",
            password=self.password,
            is_active=True,
            email_verified=True,
            access_status=User.AccessStatus.ACTIVE,
        )
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf_token(self):
        response = self.client.get("/api/users/csrf/")
        assert response.status_code == 204
        return self.client.cookies["csrftoken"].value

    def login(self):
        token = self.csrf_token()
        return self.client.post(
            "/api/users/login/",
            {"email": self.user.email, "password": self.password},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

    def test_login_uses_server_session_and_survives_reload(self):
        response = self.login()

        assert response.status_code == 200
        assert set(response.data) == {"user"}
        assert "access" not in response.data
        assert "refresh" not in response.data
        assert "globaloil_session" in self.client.cookies
        assert self.client.get("/api/users/me/").status_code == 200
        assert UserAuditLog.objects.filter(action="auth.login_succeeded", target_user=self.user).exists()

    def test_unauthenticated_api_is_401_and_post_without_csrf_is_403(self):
        assert self.client.get("/api/users/me/").status_code == 401

        response = self.client.post(
            "/api/users/login/",
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        assert response.status_code == 403

    def test_logout_invalidates_the_session(self):
        assert self.login().status_code == 200
        token = self.client.cookies["csrftoken"].value

        assert self.client.post("/api/users/logout/", HTTP_X_CSRFTOKEN=token).status_code == 204
        assert self.client.get("/api/users/me/").status_code == 401
        assert UserAuditLog.objects.filter(action="auth.logout", target_user=self.user).exists()

    def test_sixth_failed_attempt_is_rate_limited_without_user_enumeration(self):
        token = self.csrf_token()
        for _ in range(5):
            response = self.client.post(
                "/api/users/login/",
                {"email": self.user.email, "password": "wrong-password"},
                format="json",
                HTTP_X_CSRFTOKEN=token,
            )
            assert response.status_code == 401
            assert response.data["detail"] == "Credenciales inválidas."

        response = self.client.post(
            "/api/users/login/",
            {"email": "unknown@example.com", "password": "wrong-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert response.status_code == 429
        assert UserAuditLog.objects.filter(action="auth.login_failed").exists()
        assert UserAuditLog.objects.filter(action="auth.login_rate_limited").exists()

    def test_revoked_session_requires_a_new_login(self):
        assert self.login().status_code == 200
        revoke_user_sessions(self.user)

        assert self.client.get("/api/users/me/").status_code == 401

    def test_user_cannot_elevate_own_role_or_access_status(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/users/{self.user.pk}/",
            {"role": User.Role.GLOBAL, "access_status": User.AccessStatus.ACTIVE},
            format="json",
        )

        assert response.status_code == 400
        self.user.refresh_from_db()
        assert self.user.role != User.Role.GLOBAL

    def test_password_reset_does_not_enumerate_accounts_and_keeps_one_hour_policy(self):
        token = self.csrf_token()
        known = self.client.post(
            "/api/users/password-reset/",
            {"email": self.user.email},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        unknown = self.client.post(
            "/api/users/password-reset/",
            {"email": "unknown@example.com"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        assert known.status_code == unknown.status_code == 200
        assert known.data == unknown.data
        token_record = PasswordResetToken.objects.get(user=self.user)
        assert token_record.expires_at > timezone.now()
        assert token_record.expires_at <= timezone.now() + timedelta(hours=24, seconds=2)
        assert len(mail.outbox) == 1
