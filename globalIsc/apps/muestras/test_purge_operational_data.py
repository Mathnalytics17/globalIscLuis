from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.misc.api.models.companies.index import Empresa
from apps.activesTree.api.models.index import PuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.muestras.api.models.auditoria import EventoAuditoriaOperativa
from apps.muestras.api.models.importaciones import CorridaImportacion
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.resultado.api.models.index import VersionInterpretacion
from apps.users.api.models.index import (
    SecurityPermission,
    SecurityRole,
    SecurityRolePermission,
    User,
    UserCompanyProfile,
)


class PurgeOperationalDataCommandTests(TestCase):
    def setUp(self):
        self.company = Empresa.objects.create(nombre="Empresa de limpieza", email="limpieza@example.com")
        self.user = User.objects.create_user(
            email="limpieza@example.com",
            password="test-password",
            empresa=self.company,
        )
        self.batch = LoteMuestras.objects.create(
            id="L20268888",
            cliente_empresa=self.company,
            fecha_envio=timezone.localdate(),
            usuario_registro=self.user,
        )
        self.sample = Muestra.objects.create(
            id="M20268888",
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )
        VersionInterpretacion.objects.create(muestra=self.sample, version=1, contenido={})
        EventoAuditoriaOperativa.objects.create(
            actor=self.user,
            empresa=self.company,
            muestra=self.sample,
            tipo_entidad="muestra",
            entidad_id=self.sample.id,
            accion="muestra.creada",
        )
        CorridaImportacion.objects.create(
            empresa=self.company,
            actor=self.user,
            archivo_nombre="operacion-demo.xlsx",
        )

    def test_dry_run_is_non_destructive_and_includes_all_operational_traces(self):
        output = StringIO()

        call_command("purge_operational_data", "--dry-run", stdout=output)

        text = output.getvalue()
        self.assertIn("resultado.VersionInterpretacion: 1", text)
        self.assertIn("muestras.EventoAuditoriaOperativa: 1", text)
        self.assertIn("muestras.CorridaImportacion: 1", text)
        self.assertTrue(Muestra.objects.filter(pk=self.sample.pk).exists())
        self.assertTrue(VersionInterpretacion.objects.filter(muestra=self.sample).exists())

    def test_confirmed_purge_preserves_security_and_company_but_removes_operation(self):
        call_command("purge_operational_data", "--yes", stdout=StringIO())

        self.assertFalse(Muestra.objects.exists())
        self.assertFalse(VersionInterpretacion.objects.exists())
        self.assertFalse(EventoAuditoriaOperativa.objects.exists())
        self.assertFalse(CorridaImportacion.objects.exists())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Empresa.objects.filter(pk=self.company.pk).exists())


class ResetToSecurityBaselineCommandTests(TestCase):
    def setUp(self):
        self.company = Empresa.objects.create(nombre="Empresa reinicio", email="reinicio@example.com")
        self.user = User.objects.create_user(
            email="reinicio@example.com",
            password="test-password",
            empresa=self.company,
            home_path="/muestras/lotes",
            data_scope_override=User.DataScopeOverride.OWN_COMPANY,
        )
        self.role = SecurityRole.objects.create(
            name="Rol preservado", code="rol-preservado", scope=SecurityRole.Scope.GLOBAL,
        )
        self.permission = SecurityPermission.objects.create(
            module="prueba", action="ver", code="prueba.ver",
        )
        SecurityRolePermission.objects.create(role=self.role, permission=self.permission)
        UserCompanyProfile.objects.create(
            user=self.user,
            empresa=self.company,
            role=self.role,
            status=UserCompanyProfile.Status.ACTIVE,
        )
        self.machine = Maquina.objects.create(empresa=self.company, nombre="Activo reinicio")
        PuntoMuestreo.objects.create(maquina=self.machine, nombre="Punto reinicio")
        self.batch = LoteMuestras.objects.create(
            id="L20267777", cliente_empresa=self.company,
            fecha_envio=timezone.localdate(), usuario_registro=self.user,
        )
        Muestra.objects.create(
            id="M20267777", lote=self.batch,
            fecha_toma=timezone.now(), usuario_registro=self.user,
        )

    def test_dry_run_preserves_everything(self):
        output = StringIO()
        call_command("reset_to_security_baseline", "--dry-run", stdout=output)

        # The baseline now includes the Global Oil internal company created by
        # migration 0019, in addition to this test's customer company.
        self.assertIn("misc.Empresa: 2", output.getvalue())
        self.assertIn("activesTree.Maquina: 1", output.getvalue())
        self.assertTrue(Empresa.objects.filter(pk=self.company.pk).exists())
        self.assertTrue(UserCompanyProfile.objects.filter(user=self.user).exists())

    def test_confirmed_reset_keeps_users_and_rbac_only(self):
        call_command("reset_to_security_baseline", "--yes", stdout=StringIO())

        self.user.refresh_from_db()
        self.assertIsNone(self.user.empresa_id)
        self.assertEqual(self.user.home_path, "")
        self.assertEqual(self.user.data_scope_override, "")
        self.assertFalse(Empresa.objects.exists())
        self.assertFalse(Maquina.objects.exists())
        self.assertFalse(PuntoMuestreo.objects.exists())
        self.assertFalse(LoteMuestras.objects.exists())
        self.assertFalse(UserCompanyProfile.objects.exists())
        self.assertTrue(SecurityRole.objects.filter(pk=self.role.pk).exists())
        self.assertTrue(SecurityPermission.objects.filter(pk=self.permission.pk).exists())
        self.assertTrue(SecurityRolePermission.objects.filter(role=self.role, permission=self.permission).exists())


class ResetToUsersAndCompaniesTests(TestCase):
    def setUp(self):
        self.company = Empresa.objects.create(nombre="Empresa preservada")
        self.user = User.objects.create_user(
            email="preservado@example.com", password="test-password", empresa=self.company,
        )
        self.role = SecurityRole.objects.create(
            name="Rol preservado", code="rol-para-reinicio", scope=SecurityRole.Scope.COMPANY,
        )
        UserCompanyProfile.objects.create(
            user=self.user, empresa=self.company, role=self.role,
            status=UserCompanyProfile.Status.ACTIVE,
        )
        machine = Maquina.objects.create(empresa=self.company, nombre="Activo temporal")
        PuntoMuestreo.objects.create(maquina=machine, nombre="Punto temporal")
        batch = LoteMuestras.objects.create(
            id="L20267778", cliente_empresa=self.company,
            fecha_envio=timezone.localdate(), usuario_registro=self.user,
        )
        Muestra.objects.create(
            id="M20267778", lote=batch, fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )

    def test_reset_preserves_users_companies_and_memberships_only(self):
        call_command("reset_to_users_and_companies", "--yes", stdout=StringIO())

        self.assertTrue(Empresa.objects.filter(pk=self.company.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.user.pk, empresa=self.company).exists())
        self.assertTrue(UserCompanyProfile.objects.filter(user=self.user, empresa=self.company).exists())
        self.assertFalse(Maquina.objects.exists())
        self.assertFalse(PuntoMuestreo.objects.exists())
        self.assertFalse(LoteMuestras.objects.exists())
        self.assertFalse(Muestra.objects.exists())
