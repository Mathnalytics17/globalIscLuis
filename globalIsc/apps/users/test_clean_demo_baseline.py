import os
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.misc.api.models.companies.index import Empresa
from apps.users.api.models.index import User, UserCompanyProfile


class CleanDemoBaselineCommandTests(TestCase):
    @patch.dict(os.environ, {"DEMO_DEFAULT_PASSWORD": "Demo-clean-password-123!"})
    def test_creates_one_global_admin_and_three_coherent_tenants(self):
        call_command("seed_clean_demo_baseline", "--yes", "--reset-passwords", stdout=StringIO())

        self.assertEqual(Empresa.objects.count(), 4)
        self.assertEqual(User.objects.count(), 10)
        global_admin = User.objects.get(email="admin@globaloil.local")
        self.assertEqual(global_admin.role, User.Role.GLOBAL)
        self.assertEqual(global_admin.empresa.nombre, "Global Oil")
        self.assertTrue(global_admin.empresa.is_internal)
        self.assertTrue(global_admin.check_password("Demo-clean-password-123!"))
        global_profile = UserCompanyProfile.objects.get(user=global_admin, empresa=global_admin.empresa)
        self.assertEqual(global_profile.role.code, "admin_global")
        for company in Empresa.objects.filter(is_internal=False):
            self.assertIn(company.nombre, {"Empresa Minera Demo", "Taller Demo", "Industria Demo"})
            profiles = UserCompanyProfile.objects.filter(empresa=company, status=UserCompanyProfile.Status.ACTIVE)
            self.assertEqual(profiles.count(), 3)
            self.assertEqual(profiles.filter(is_company_admin=True).count(), 1)
            self.assertEqual(set(profiles.values_list("role__code", flat=True)), {
                "admin_empresa", "empresa_consulta", "empresa_carga_muestras",
            })
        self.assertFalse(User.objects.filter(role=User.Role.LABORATORISTA).exists())

    @patch.dict(os.environ, {"DEMO_DEFAULT_PASSWORD": "Demo-clean-password-123!"})
    def test_requires_explicit_confirmation(self):
        with self.assertRaisesMessage(Exception, "Confirme con --yes"):
            call_command("seed_clean_demo_baseline", stdout=StringIO())
