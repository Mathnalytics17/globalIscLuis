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
from apps.users.api.models.index import SecurityPermission, SecurityRole, SecurityRolePermission, UserCompanyProfile, UserDataScopeCompany, UserInvitation
from apps.users.api.serializers.index import UserSerializer
from apps.users.api.data_scope import accessible_company_ids, scope_queryset
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

    def test_laboratorist_has_the_report_authoring_workflow_not_delivery_decisions(self):
        seed_default_permissions()
        labor = SecurityRole.objects.get(code="laboratorista")
        codes = set(labor.role_permissions.filter(allowed=True).values_list("permission__code", flat=True))

        self.assertTrue({
            "reportes.ver", "reportes.generar", "reportes.previsualizar",
            "reportes.subir_firma", "reportes.descargar_pdf", "reportes.ver_versiones",
        }.issubset(codes))
        self.assertNotIn("reportes.aprobar", codes)
        self.assertNotIn("reportes.publicar_cliente", codes)

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


class InternalGlobalOilInvitationTests(TestCase):
    def setUp(self):
        seed_default_permissions()
        self.global_company = Empresa.objects.create(
            nombre="Global Oil Interna",
            nit="GO-INTERNA-TEST",
            is_internal=True,
        )
        self.customer_company = Empresa.objects.create(nombre="Cliente Test", nit="CLIENTE-TEST")
        self.labor_role = SecurityRole.objects.get(code="laboratorista")
        self.company_role = SecurityRole.objects.get(code="empresa_consulta")

    @patch("apps.users.api.services.deliver_invitation_email", return_value=(True, ""))
    def test_internal_role_is_invited_to_global_oil_and_keeps_its_legacy_role(self, _delivery):
        invitation = create_invitation(
            "nuevo.laboratorista@example.com",
            self.global_company,
            role=self.labor_role,
        )
        accepted = accept_invitation(
            invitation.token,
            "Nuevo",
            "Laboratorista",
            "Safe-password-123!",
        )
        accepted.refresh_from_db()
        self.assertEqual(accepted.empresa_id, self.global_company.id)
        self.assertEqual(accepted.role, User.Role.LABORATORISTA)
        self.assertEqual(
            accepted.company_profiles.get(empresa=self.global_company).role_id,
            self.labor_role.id,
        )

    def test_internal_and_customer_roles_cannot_cross_company_boundaries(self):
        with self.assertRaisesMessage(ValueError, "roles internos"):
            create_invitation("wrong-internal@example.com", self.customer_company, role=self.labor_role)
        with self.assertRaisesMessage(ValueError, "empresa cliente"):
            create_invitation("wrong-company@example.com", self.global_company, role=self.company_role)


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
    def test_reinvitation_keeps_an_existing_password(self, _delivery):
        original_password = "Old-password-123!"
        invitation = create_invitation(self.user.email, self.company_a, role=self.role)

        self.assertFalse(invitation.metadata["requires_password"])
        accepted = accept_invitation(
            invitation.token,
            "Ana",
            "Prueba",
            "",
        )

        accepted.refresh_from_db()
        self.assertTrue(accepted.check_password(original_password))
        self.assertTrue(accepted.is_active)

    @patch("apps.users.api.services.deliver_invitation_email", return_value=(True, ""))
    def test_new_invitation_requires_a_password(self, _delivery):
        invitation = create_invitation("nueva@example.com", self.company_a, role=self.role)

        self.assertTrue(invitation.metadata["requires_password"])
        with self.assertRaisesMessage(ValueError, "requiere que defina una contraseña"):
            accept_invitation(invitation.token, "Nueva", "Persona", "")

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


class InternalUserReinviteTests(TestCase):
    def setUp(self):
        seed_default_permissions()
        self.global_company = Empresa.objects.create(
            nombre="Global Oil Reinvite",
            nit="GO-REINVITE-TEST",
            is_internal=True,
        )
        self.labor_role = SecurityRole.objects.get(code="laboratorista")
        self.admin = User.objects.create_user(
            email="admin-reinvite@example.com",
            password="Test-password-123!",
            role=User.Role.GLOBAL,
            is_active=True,
        )
        self.target = User.objects.create_user(
            email="laboratorista-reinvite@example.com",
            password="Test-password-123!",
            empresa=self.global_company,
            role=User.Role.LABORATORISTA,
            is_active=False,
            access_status=User.AccessStatus.PENDING_INVITATION,
        )
        UserCompanyProfile.objects.create(
            user=self.target,
            empresa=self.global_company,
            role=self.labor_role,
            status=UserCompanyProfile.Status.PENDING,
        )

    @patch("apps.users.api.services.deliver_invitation_email", return_value=(True, ""))
    def test_reinvite_keeps_internal_role_when_client_omits_it(self, _delivery):
        client = APIClient()
        client.force_authenticate(self.admin)

        response = client.post(f"/api/security/users/{self.target.id}/reinvite/", {}, format="json")

        self.assertEqual(response.status_code, 201)
        invitation = UserInvitation.objects.get(pk=response.data["id"])
        self.assertEqual(invitation.empresa_id, self.global_company.id)
        self.assertEqual(invitation.role_id, self.labor_role.id)

    @patch("apps.users.api.services.deliver_invitation_email", return_value=(True, ""))
    def test_reinvite_ignores_stale_role_posted_for_same_company(self, _delivery):
        company_role = SecurityRole.objects.get(code="empresa_consulta")
        client = APIClient()
        client.force_authenticate(self.admin)

        response = client.post(
            f"/api/security/users/{self.target.id}/reinvite/",
            {"empresa": self.global_company.id, "role": company_role.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(UserInvitation.objects.get(pk=response.data["id"]).role_id, self.labor_role.id)

    def test_user_payload_exposes_editable_profile_relation_ids(self):
        profile = UserSerializer(self.target).data["profile"]
        self.assertEqual(profile["empresa"], self.global_company.id)
        self.assertEqual(profile["role"], self.labor_role.id)

    def test_user_payload_prefers_current_company_over_historical_profile(self):
        customer = Empresa.objects.create(nombre="Empresa histórica", nit="HISTORICAL-TEST")
        customer_role = SecurityRole.objects.get(code="empresa_consulta")
        current_profile = self.target.company_profiles.get(empresa=self.global_company)
        current_profile.status = UserCompanyProfile.Status.REMOVED
        current_profile.save(update_fields=["status", "updated_at"])
        UserCompanyProfile.objects.create(
            user=self.target,
            empresa=customer,
            role=customer_role,
            status=UserCompanyProfile.Status.ACTIVE,
        )

        profile = UserSerializer(self.target).data["profile"]

        self.assertEqual(profile["empresa"], self.global_company.id)
        self.assertEqual(profile["role"], self.labor_role.id)


class DataScopeTests(TestCase):
    def setUp(self):
        self.company_a = Empresa.objects.create(nombre="Alfa")
        self.company_b = Empresa.objects.create(nombre="Beta")
        self.company_c = Empresa.objects.create(nombre="Gamma")
        self.role = SecurityRole.objects.create(
            name="Analista multiempresa",
            code="analista-multiempresa-test",
            scope=SecurityRole.Scope.INTERNAL,
            data_scope=SecurityRole.DataScope.ASSIGNED_COMPANIES,
        )
        self.user = User.objects.create_user(
            email="analista@example.com",
            password="Test-password-123!",
            empresa=self.company_a,
            is_active=True,
        )
        UserCompanyProfile.objects.create(
            user=self.user,
            empresa=self.company_a,
            role=self.role,
            status=UserCompanyProfile.Status.ACTIVE,
        )

    def test_assigned_companies_scope_is_explicit_and_reusable_for_any_queryset(self):
        UserDataScopeCompany.objects.create(user=self.user, empresa=self.company_b)
        self.assertEqual(accessible_company_ids(self.user), {self.company_b.id})
        visible = scope_queryset(Empresa.objects.order_by("id"), self.user, "id")
        self.assertEqual(list(visible.values_list("id", flat=True)), [self.company_b.id])

    def test_user_override_can_grant_all_companies_without_changing_role_permissions(self):
        self.user.data_scope_override = SecurityRole.DataScope.ALL_COMPANIES
        self.user.save(update_fields=["data_scope_override"])
        self.assertIsNone(accessible_company_ids(self.user))
        # The unrestricted scope also includes the Global Oil internal company
        # established by migration 0019.
        self.assertEqual(scope_queryset(Empresa.objects.all(), self.user, "id").count(), 4)


class UserDirectoryPermissionTests(TestCase):
    """The old /users/ routes must enforce the same permission as the RBAC UI."""

    def setUp(self):
        seed_default_permissions()
        self.company = Empresa.objects.create(nombre="Empresa directorio")
        self.directory_role = SecurityRole.objects.create(
            name="Rol directorio de prueba",
            code="rol-directorio-prueba",
            scope=SecurityRole.Scope.COMPANY,
        )
        SecurityRolePermission.objects.create(
            role=self.directory_role,
            permission=SecurityPermission.objects.get(code="empresas.ver_usuarios"),
            allowed=True,
        )
        self.viewer = User.objects.create_user(
            email="visor-directorio@example.com", password="Test-password-123!", empresa=self.company,
        )
        self.member = User.objects.create_user(
            email="miembro-directorio@example.com", password="Test-password-123!", empresa=self.company,
        )
        self.target = User.objects.create_user(
            email="objetivo-directorio@example.com", password="Test-password-123!", empresa=self.company,
        )
        UserCompanyProfile.objects.create(
            user=self.viewer, empresa=self.company, role=self.directory_role,
            status=UserCompanyProfile.Status.ACTIVE,
        )

    def test_member_without_directory_permission_cannot_list_or_read_colleagues(self):
        client = APIClient()
        client.force_authenticate(self.member)

        self.assertEqual(client.get("/api/users/").status_code, 403)
        self.assertEqual(client.get(f"/api/users/{self.target.pk}/").status_code, 403)
        self.assertEqual(client.get(f"/api/users/{self.member.pk}/").status_code, 200)

    def test_role_with_directory_permission_can_list_same_company_users(self):
        client = APIClient()
        client.force_authenticate(self.viewer)

        response = client.get("/api/users/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["id"] for item in response.data}, {self.viewer.id, self.member.id, self.target.id})
