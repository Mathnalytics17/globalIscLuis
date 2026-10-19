import base64
import os
import tempfile
from unittest.mock import patch

from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.misc.api.models.companies.index import Empresa
from apps.users.api.models.index import User
from apps.users.api.models.index import SecurityPermission, SecurityRole, UserCompanyProfile
from apps.users.api.services import accept_invitation, create_invitation, seed_default_permissions
from apps.users.api.views.user.index import CurrentUserView


class UserProfileSignatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="firma@example.com",
            password="test-password",
            is_active=True,
        )

    def test_user_can_upload_and_remove_default_signature(self):
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        upload = SimpleUploadedFile("firma.png", png, content_type="image/png")
        factory = APIRequestFactory()

        with tempfile.TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root,
            ALLOWED_HOSTS=["testserver"],
        ):
            upload_request = factory.patch(
                "/api/users/me/",
                {"firma_predeterminada": upload},
                format="multipart",
            )
            force_authenticate(upload_request, user=self.user)
            upload_response = CurrentUserView.as_view()(upload_request)

            self.assertEqual(upload_response.status_code, 200)
            self.assertIn("/media/firmas_usuarios/", upload_response.data["firma_predeterminada"])

            remove_request = factory.patch(
                "/api/users/me/",
                {"firma_predeterminada": None},
                format="json",
            )
            force_authenticate(remove_request, user=self.user)
            remove_response = CurrentUserView.as_view()(remove_request)

            self.assertEqual(remove_response.status_code, 200)
            self.assertIsNone(remove_response.data["firma_predeterminada"])

    def test_user_can_save_only_an_allowed_home_path(self):
        factory = APIRequestFactory()
        request = factory.patch("/api/users/me/", {"home_path": "/muestras/laboratorio"}, format="json")
        force_authenticate(request, user=self.user)

        response = CurrentUserView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["home_path"], "/muestras/laboratorio")

        invalid = factory.patch("/api/users/me/", {"home_path": "https://example.invalid"}, format="json")
        force_authenticate(invalid, user=self.user)
        invalid_response = CurrentUserView.as_view()(invalid)

        self.assertEqual(invalid_response.status_code, 400)
        self.assertIn("home_path", invalid_response.data)


class AccessBaselineCommandTests(TestCase):
    def test_sample_loader_can_view_reports_without_inheriting_traceability(self):
        seed_default_permissions()
        loader = SecurityRole.objects.get(code="empresa_carga_muestras")
        admin = SecurityRole.objects.get(code="admin_empresa")

        loader_codes = set(
            loader.role_permissions.filter(allowed=True).values_list("permission__code", flat=True)
        )
        admin_codes = set(
            admin.role_permissions.filter(allowed=True).values_list("permission__code", flat=True)
        )

        self.assertIn("reportes.ver", loader_codes)
        self.assertNotIn("trazabilidad.ver", loader_codes)
        self.assertIn("trazabilidad.ver", admin_codes)
        self.assertIn("importaciones.ver", admin_codes)
        self.assertEqual(SecurityRole.objects.get(code="laboratorista").default_home_path, "/muestras/laboratorio")

    def test_sample_loader_is_denied_traceability_but_can_open_reports(self):
        with patch.dict(os.environ, {"DEMO_DEFAULT_PASSWORD": "Test-Only-Demo-Password!"}):
            call_command("seed_access_baseline", with_demo_accounts=True)

        client = APIClient()
        client.force_authenticate(User.objects.get(email="muestras@minera.demo"))

        self.assertEqual(client.get("/api/lubrication/traceability/").status_code, 403)
        self.assertEqual(client.get("/api/lubrication/reports/dashboard/").status_code, 200)

    def test_operational_dashboard_is_global_only(self):
        with patch.dict(os.environ, {"DEMO_DEFAULT_PASSWORD": "Test-Only-Demo-Password!"}):
            call_command("seed_access_baseline", with_demo_accounts=True)

        client = APIClient()
        client.force_authenticate(User.objects.get(email="laboratorio@globaloil.demo"))
        self.assertEqual(client.get("/api/dashboard/operational-center/").status_code, 403)

        client.force_authenticate(User.objects.get(email="admin.global@globaloil.demo"))
        self.assertEqual(client.get("/api/dashboard/operational-center/").status_code, 200)

    def test_demo_seed_is_idempotent_and_uses_environment_password(self):
        password = "Test-Only-Demo-Password!"
        with patch.dict(os.environ, {"DEMO_DEFAULT_PASSWORD": password}):
            call_command("seed_access_baseline", with_demo_accounts=True)
            first_counts = (
                User.objects.count(),
                SecurityRole.objects.count(),
                SecurityPermission.objects.count(),
            )
            call_command("seed_access_baseline", with_demo_accounts=True)

        self.assertEqual(
            first_counts,
            (User.objects.count(), SecurityRole.objects.count(), SecurityPermission.objects.count()),
        )
        admin = User.objects.get(email="admin.global@globaloil.demo")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password(password))


class UserReinvitationLifecycleTests(TestCase):
    def setUp(self):
        self.company_a = Empresa.objects.create(nombre="Empresa A")
        self.company_b = Empresa.objects.create(nombre="Empresa B")
        self.role = SecurityRole.objects.create(
            name="Administrador empresa",
            code="admin-empresa-test",
            scope=SecurityRole.Scope.COMPANY,
        )
        self.user = User.objects.create_user(
            email="reutilizable@example.com",
            password="Old-password-123!",
            empresa=self.company_a,
            is_active=False,
            access_status=User.AccessStatus.DISABLED,
        )
        UserCompanyProfile.objects.create(
            user=self.user,
            empresa=self.company_a,
            role=self.role,
            status=UserCompanyProfile.Status.REMOVED,
        )

    @patch("apps.users.api.services.deliver_invitation_email", return_value=(True, ""))
    def test_disabled_user_can_be_reinvited_with_same_email(self, _delivery):
        invitation = create_invitation(self.user.email, self.company_a, role=self.role)
        accepted = accept_invitation(
            invitation.token,
            "Ana",
            "Prueba",
            "New-password-123!",
        )
        accepted.refresh_from_db()
        profile = UserCompanyProfile.objects.get(user=accepted, empresa=self.company_a)
        self.assertTrue(accepted.is_active)
        self.assertEqual(accepted.access_status, User.AccessStatus.ACTIVE)
        self.assertEqual(profile.status, UserCompanyProfile.Status.ACTIVE)

    @patch("apps.users.api.services.deliver_invitation_email", return_value=(True, ""))
    def test_company_transfer_only_changes_membership_after_acceptance(self, _delivery):
        with self.assertRaises(ValueError):
            create_invitation(self.user.email, self.company_b, role=self.role)

        invitation = create_invitation(
            self.user.email,
            self.company_b,
            role=self.role,
            allow_company_transfer=True,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.empresa_id, self.company_a.id)

        accepted = accept_invitation(
            invitation.token,
            "Ana",
            "Transferida",
            "New-password-123!",
        )
        accepted.refresh_from_db()
        self.assertEqual(accepted.empresa_id, self.company_b.id)
        self.assertEqual(
            UserCompanyProfile.objects.get(user=accepted, empresa=self.company_a).status,
            UserCompanyProfile.Status.REMOVED,
        )
        self.assertEqual(
            UserCompanyProfile.objects.get(user=accepted, empresa=self.company_b).status,
            UserCompanyProfile.Status.ACTIVE,
        )
