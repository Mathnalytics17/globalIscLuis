from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoItem,
    EscalaComparacion,
    EscalaComparacionItem,
    PruebaFuenteLimite,
    PruebaLimiteCampo,
    CriterioEvaluacionLimite,
)
from apps.misc.api.models.lotesPruebasPredefinidos.index import LotePruebasPredefinido
from apps.misc.api.models.pruebas.index import Prueba, PruebaResultado, PruebaResultadoDivision, PruebaResultadoComponente
from apps.misc.api.models.technicalCatalogs.index import Condicion, EquipoPrueba, MetodoEquipo, Unidad
from apps.misc.api.models.tipoGestionMuestra.index import TipoGestionMuestra
from apps.users.api.models.index import User, UserInvitation


class ResetGlobalOilFlowCommandTests(TestCase):
    def test_command_builds_integrated_demo_without_removing_users(self):
        user = User.objects.create_user(
            email="seed-keeper@example.com",
            password="test-password",
            is_superuser=True,
        )

        call_command("reset_globaloil_flow", "--yes", stdout=StringIO())

        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertTrue(Prueba.objects.filter(acronimo="FERRO", activo=True).exists())
        self.assertTrue(Prueba.objects.filter(acronimo="ESP", activo=True).exists())
        ferro = Prueba.objects.get(acronimo="FERRO")
        self.assertEqual(ferro.resultados.filter(activo=True).count(), 4)
        self.assertEqual(
            PruebaResultadoComponente.objects.filter(
                division__resultado__prueba=ferro,
                activo=True,
            ).count(),
            12,
        )
        source = PruebaFuenteLimite.objects.get(prueba=ferro, activo=True)
        self.assertNotIn("resultados_amarillos_para_critico", source.configuracion_regla)
        self.assertEqual(source.reglas_resultados, {})


class DynamicTechnicalConfigApiTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(nombre="Global Oil Config Test")
        self.user = User.objects.create_user(
            email="technical-config@example.com",
            password="test-password",
            empresa=empresa,
            is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_evaluation_criterion_stores_limit_matrix_values(self):
        catalog = CatalogoTecnico.objects.create(
            nombre="Nivel de desempeno",
            codigo="nivel_desempeno",
            tipo_muestra="aceite",
        )
        item = CatalogoTecnicoItem.objects.create(catalogo=catalog, nombre="API SN")
        test = Prueba.objects.create(nombre_variable="Espuma", acronimo="ESP")
        source = PruebaFuenteLimite.objects.create(prueba=test, catalogo_fuente=catalog)
        field = PruebaLimiteCampo.objects.create(
            fuente_limite=source,
            nombre="Secuencia I FI",
            codigo="secuencia_i_fi",
            operador="max",
        )
        criterion = CriterioEvaluacionLimite.objects.create(
            fuente_limite=source,
            nombre=item.nombre,
            codigo=item.codigo,
            tipo_criterio="catalogo_item",
            catalogo_item=item,
            valores_limite={field.codigo: "12"},
        )

        self.assertEqual(criterion.valores_limite[field.codigo], "12")

    def test_atomic_limit_configuration_creates_range_and_criterion(self):
        test = Prueba.objects.create(nombre_variable="Viscosidad", acronimo="VISC")
        result = PruebaResultado.objects.create(prueba=test, nombre="Resultado")
        division = PruebaResultadoDivision.objects.create(resultado=result, nombre="Principal", es_principal=True)
        component = PruebaResultadoComponente.objects.create(division=division, nombre="Valor")

        response = self.client.post(
            "/api/technical-config/limit-sources/configure/",
            {
                "prueba": test.id,
                "fuente": "criterios",
                "modo_seleccion": "seleccionar_asignacion",
                "campos": [{
                    "codigo": "resultado_principal_valor",
                    "resultado": result.id,
                    "componente": component.id,
                    "operador": "between",
                    "tipo_comparacion": "numerica",
                    "origen_limite": "catalogo",
                    "valor_global": {
                        "min_critico": "",
                        "min_aceptable": "",
                        "max_aceptable": "",
                        "max_critico": "",
                        "usar_amarillo": True,
                    },
                }],
                "criterios": [{
                    "nombre": "Rango normal",
                    "valores": {
                        "resultado_principal_valor": {
                            "min_aceptable": "10",
                            "max_aceptable": "20",
                            "usar_amarillo": False,
                        },
                    },
                }],
                "decision": {"modo": "semaforo", "version": 2},
                "publicar": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        source = PruebaFuenteLimite.objects.get(prueba=test, activo=True)
        self.assertTrue(source.publicada)
        self.assertEqual(source.campos_limite.filter(activo=True).count(), 1)
        self.assertEqual(source.campos_limite.get(activo=True).operador, "between")
        self.assertEqual(
            source.criterios.get().valores_limite["resultado_principal_valor"]["min_aceptable"],
            "10",
        )

    def test_editing_compound_test_relinks_fields_without_losing_semaphore_bands(self):
        catalog = CatalogoTecnico.objects.create(
            nombre="Grado de viscosidad",
            codigo="grado_viscosidad",
            tipo_muestra="aceite",
        )
        item = CatalogoTecnicoItem.objects.create(catalogo=catalog, nombre="SAE 10W-60")
        test = Prueba.objects.create(nombre_variable="Espuma", acronimo="ESP-RELINK")
        result = PruebaResultado.objects.create(
            prueba=test,
            nombre="espuma i",
            unidad_medida="ml/ml",
        )
        division = PruebaResultadoDivision.objects.create(
            resultado=result,
            nombre=None,
            es_principal=True,
        )
        component_ei = PruebaResultadoComponente.objects.create(
            division=division,
            nombre="ei",
        )
        component_fi = PruebaResultadoComponente.objects.create(
            division=division,
            nombre="fi",
        )
        source = PruebaFuenteLimite.objects.create(
            prueba=test,
            tipo_limite="catalogo",
            catalogo_fuente=catalog,
            configuracion_regla={
                "modo": "semaforo",
                "version": 2,
                "campos": [
                    {
                        "codigo": "espuma_i_ei",
                        "nombre": "ei",
                        "resultado": result.id,
                        "division": division.id,
                        "componente": component_ei.id,
                        "operador": "between",
                        "origen_limite": "catalogo",
                        "tipo_comparacion": "numerica",
                        "valor_global": {"usar_amarillo": True},
                    },
                    {
                        "codigo": "espuma_i_fi",
                        "nombre": "fi",
                        "resultado": result.id,
                        "division": division.id,
                        "componente": component_fi.id,
                        "operador": "max",
                        "origen_limite": "catalogo",
                        "tipo_comparacion": "numerica",
                        "valor_global": {},
                    },
                ],
            },
        )
        for order, (code, component, operator) in enumerate([
            ("espuma_i_ei", component_ei, "between"),
            ("espuma_i_fi", component_fi, "max"),
        ], start=1):
            PruebaLimiteCampo.objects.create(
                fuente_limite=source,
                nombre=code,
                codigo=code,
                operador=operator,
                resultado=result,
                division=division,
                componente=component,
                orden=order,
            )
        bands = {
            "espuma_i_ei": {
                "min_critico": "11",
                "min_aceptable": "22",
                "max_aceptable": "23",
                "max_critico": "33",
                "usar_amarillo": True,
            },
            "espuma_i_fi": {
                "max_aceptable": "0",
                "max_critico": "1",
                "usar_amarillo": True,
            },
        }
        criterion = CriterioEvaluacionLimite.objects.create(
            fuente_limite=source,
            nombre=item.nombre,
            codigo="sae_10w_60",
            tipo_criterio="catalogo_item",
            catalogo_item=item,
            valores_limite=bands,
        )
        old_component_ids = {component_ei.id, component_fi.id}

        response = self.client.patch(
            f"/api/misc/tests/{test.id}/",
            {
                "resultados": [{
                    "nombre": "espuma i",
                    "unidad_medida": "ml/ml",
                    "orden": 1,
                    "divisiones": [{
                        "nombre": None,
                        "es_principal": True,
                        "orden": 1,
                        "componentes": [
                            {"temp_id": "ei", "nombre": "ei", "tipo_dato": "numerico", "orden": 1},
                            {"temp_id": "fi", "nombre": "fi", "tipo_dato": "numerico", "orden": 2},
                        ],
                        "separadores": [],
                        "disposiciones": [],
                    }],
                }],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        source.refresh_from_db()
        criterion.refresh_from_db()
        current_components = set(
            test.resultados.values_list("divisiones__componentes__id", flat=True)
        )
        self.assertTrue(current_components.isdisjoint(old_component_ids))
        self.assertEqual(criterion.valores_limite, bands)
        self.assertEqual(
            {field["codigo"] for field in source.configuracion_regla["campos"]},
            {"espuma_i_ei", "espuma_i_fi"},
        )
        self.assertEqual(
            {
                field.componente_id
                for field in source.campos_limite.filter(activo=True)
            },
            current_components,
        )

    def test_mixed_test_round_trip_preserves_all_results_fields_and_layout(self):
        scale = EscalaComparacion.objects.create(
            nombre="Severidad de desgaste",
            codigo="severidad_desgaste_test",
        )
        EscalaComparacionItem.objects.create(
            escala=scale,
            etiqueta="Leve",
            valor_normalizado="leve",
            orden=1,
        )
        EscalaComparacionItem.objects.create(
            escala=scale,
            etiqueta="Crítico",
            valor_normalizado="critico",
            orden=2,
        )
        test = Prueba.objects.create(nombre_variable="Panel integral mixto", acronimo="PIM-ROUNDTRIP")

        payload = {
            "resultados": [
                {
                    "temp_id": "result_particles",
                    "nombre": "Partículas metálicas",
                    "unidad_medida": "partículas/ml",
                    "orden": 1,
                    "divisiones": [
                        {
                            "temp_id": "division_primary",
                            "nombre": "Conteo principal",
                            "es_principal": True,
                            "orden": 1,
                            "componentes": [
                                {
                                    "temp_id": "large",
                                    "nombre": "Ferrosas grandes",
                                    "tipo_dato": "numerico",
                                    "opciones_resultado": {"decimales": 0, "minimo": 0},
                                    "orden": 1,
                                },
                                {
                                    "temp_id": "fine",
                                    "nombre": "Ferrosas finas",
                                    "tipo_dato": "numerico",
                                    "orden": 2,
                                },
                            ],
                            "separadores": [{"temp_id": "slash", "simbolo": "/", "orden": 1}],
                            "disposiciones": [
                                {
                                    "temp_id": "particle_layout",
                                    "nombre": "Conteo",
                                    "orden": 1,
                                    "items": [
                                        {"tipo": "componente", "componente": "large", "orden": 1},
                                        {"tipo": "separador", "separador": "slash", "orden": 2},
                                        {"tipo": "componente", "componente": "fine", "orden": 3},
                                    ],
                                }
                            ],
                        },
                        {
                            "temp_id": "division_secondary",
                            "nombre": "Confirmación",
                            "es_principal": False,
                            "orden": 2,
                            "componentes": [
                                {"temp_id": "confirmation", "nombre": "Confirmado", "tipo_dato": "booleano", "etiqueta_verdadero": "Presente", "etiqueta_falso": "Ausente", "orden": 1}
                            ],
                            "separadores": [],
                            "disposiciones": [],
                        },
                    ],
                },
                {
                    "temp_id": "result_morphology",
                    "nombre": "Morfología",
                    "orden": 2,
                    "divisiones": [{
                        "temp_id": "morphology_primary",
                        "es_principal": True,
                        "orden": 1,
                        "componentes": [{"temp_id": "wear", "nombre": "Desgaste", "tipo_dato": "escala", "escala_comparacion": scale.id, "orden": 1}],
                        "separadores": [],
                        "disposiciones": [],
                    }],
                },
                {
                    "temp_id": "result_notes",
                    "nombre": "Observación",
                    "orden": 3,
                    "divisiones": [{
                        "temp_id": "notes_primary",
                        "es_principal": True,
                        "orden": 1,
                        "componentes": [{"temp_id": "comment", "nombre": "Comentario técnico", "tipo_dato": "comentario", "requiere_valor": False, "orden": 1}],
                        "separadores": [],
                        "disposiciones": [],
                    }],
                },
            ]
        }

        response = self.client.patch(f"/api/misc/tests/{test.id}/", payload, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        detail = self.client.get(f"/api/misc/tests/{test.id}/")
        self.assertEqual(detail.status_code, 200, detail.data)
        results = detail.data["resultados"]
        self.assertEqual(len(results), 3)
        self.assertEqual(len(results[0]["divisiones"]), 2)
        self.assertEqual(len(results[0]["divisiones"][0]["componentes"]), 2)
        self.assertEqual(results[0]["divisiones"][0]["componentes"][0]["opciones_resultado"], {"decimales": 0, "minimo": 0})
        self.assertEqual(results[0]["divisiones"][1]["componentes"][0]["etiqueta_verdadero"], "Presente")
        self.assertEqual(results[0]["divisiones"][1]["componentes"][0]["etiqueta_falso"], "Ausente")
        self.assertEqual(results[1]["divisiones"][0]["componentes"][0]["escala_comparacion"], scale.id)
        self.assertEqual(len(results[1]["divisiones"][0]["componentes"][0]["escala_comparacion_info"]["items"]), 2)
        self.assertFalse(results[2]["divisiones"][0]["componentes"][0]["requiere_valor"])
        layout = results[0]["divisiones"][0]["disposiciones"][0]["items"]
        self.assertEqual([item["tipo"] for item in layout], ["componente", "separador", "componente"])
        self.assertTrue(all(item.get("componente") or item.get("separador") for item in layout))


class CompanyApiTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nombre="Cliente inicial",
            nit="900001",
            direccion="Direccion inicial",
            telefono="111",
            email="inicial@example.com",
        )
        self.user = User.objects.create_user(
            email="company-editor@example.com",
            password="test-password",
            empresa=self.empresa,
            role="GLOBAL",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_partial_update_company_accepts_canonical_fields(self):
        response = self.client.patch(
            f"/api/companies/{self.empresa.id}/",
            {
                "nombre": "Cliente actualizado",
                "nit": "900002",
                "direccion": "Nueva direccion",
                "telefono": "222",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.nombre, "Cliente actualizado")
        self.assertEqual(self.empresa.nit, "900002")

    def test_partial_update_company_accepts_legacy_aliases(self):
        response = self.client.patch(
            f"/api/companies/{self.empresa.id}/",
            {
                "name": "Cliente alias",
                "address": "Direccion alias",
                "phone": "333",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.nombre, "Cliente alias")
        self.assertEqual(self.empresa.direccion, "Direccion alias")

    @patch("apps.users.api.services.send_invitation_email", side_effect=OSError("SMTP no disponible"))
    def test_create_company_does_not_return_500_when_email_delivery_fails(self, _send_mail):
        response = self.client.post(
            "/api/companies/",
            {
                "nombre": "Cliente con correo pendiente",
                "nit": "900003",
                "admin_email": "nuevo-admin@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(response.data["admin_invitation"]["email_sent"])
        self.assertEqual(response.data["admin_invitation"]["delivery_status"], "failed")
        invitation = UserInvitation.objects.get(email="nuevo-admin@example.com")
        self.assertEqual(invitation.status, UserInvitation.Status.PENDING)
        self.assertEqual(invitation.metadata["email_delivery"]["status"], "failed")

    def test_create_company_rolls_back_when_admin_email_belongs_to_another_company(self):
        User.objects.create_user(
            email="ocupado@example.com",
            password="test-password",
            empresa=self.empresa,
            role=User.Role.EMPRESA,
        )

        response = self.client.post(
            "/api/companies/",
            {
                "nombre": "Empresa que no debe persistir",
                "nit": "900004",
                "admin_email": "ocupado@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("admin_email", response.data)
        self.assertFalse(Empresa.objects.filter(nombre="Empresa que no debe persistir").exists())


class SoftDeletedTechnicalConfigTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="technical-admin@example.com",
            password="test-password",
            role=User.Role.GLOBAL,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_deleted_management_type_can_be_restored_and_edited(self):
        item = TipoGestionMuestra.objects.create(
            nombre="Gestión eliminada",
            activo=False,
            deleted_at=timezone.now(),
        )

        restored = self.client.post(
            f"/api/technical-catalogs/sample-management-types/{item.id}/restore/",
            {},
            format="json",
        )
        self.assertEqual(restored.status_code, 200, restored.data)

        item.activo = False
        item.deleted_at = timezone.now()
        item.save(update_fields=["activo", "deleted_at", "updated_at"])
        updated = self.client.patch(
            f"/api/technical-catalogs/sample-management-types/{item.id}/",
            {"nombre": "Gestión recuperada"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.data)

    def test_inactive_test_can_be_opened_and_edited(self):
        test = Prueba.objects.create(
            nombre_variable="Prueba inactiva",
            acronimo="INACTIVA-QA",
            activo=False,
        )

        detail = self.client.get(f"/api/misc/tests/{test.id}/")
        self.assertEqual(detail.status_code, 200, detail.data)
        updated = self.client.patch(
            f"/api/misc/tests/{test.id}/",
            {"nombre_variable": "Prueba inactiva editada"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.data)


class TechnicalCatalogBusinessRuleTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(nombre="Global Oil Business Rules")
        self.user = User.objects.create_user(
            email="business-rules@example.com",
            password="test-password",
            empresa=empresa,
            is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        equipo = EquipoPrueba.objects.create(codigo="VIS", nombre="Viscosimetro")
        self.metodo = MetodoEquipo.objects.create(equipo_prueba=equipo, codigo="ASTM-D445", nombre="ASTM D445")
        self.unit = Unidad.objects.get(simbolo="cSt")
        celsius = Unidad.objects.get(simbolo="°C")
        self.condition, _ = Condicion.objects.get_or_create(
            nombre="Temperatura 40 C",
            magnitud="temperatura",
            valor=40,
            unidad=celsius,
        )

    def test_test_creation_uses_unit_and_condition_catalogs(self):
        response = self.client.post(
            "/api/misc/tests/",
            {
                "nombre_variable": "Viscosidad 40 C",
                "acronimo": "V40",
                "metodo": self.metodo.id,
                "unidad_catalogo": self.unit.id,
                "condicion_catalogo": self.condition.id,
                "resultados": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        prueba = Prueba.objects.get(acronimo="V40")
        self.assertEqual(prueba.unidad_catalogo, self.unit)
        self.assertEqual(prueba.unidad_medida, "cSt")
        self.assertEqual(prueba.condicion_catalogo, self.condition)
        self.assertEqual(prueba.condicion, "40 °C")

        detail = self.client.get(f"/api/misc/tests/{prueba.id}/")

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["metodo"], self.metodo.id)
        self.assertEqual(detail.data["metodo_detalle"]["id"], self.metodo.id)
        self.assertEqual(detail.data["equipo"]["id"], self.metodo.equipo_prueba_id)

    def test_management_type_can_store_suggested_tests(self):
        prueba = Prueba.objects.create(
            nombre_variable="Agua",
            acronimo="H2O",
            metodo=self.metodo,
            unidad_catalogo=self.unit,
            unidad_medida=self.unit.simbolo,
        )

        response = self.client.post(
            "/api/technical-catalogs/sample-management-types/",
            {
                "nombre": "Ingreso estandar",
                "dias_habiles": 1,
                "dias_calendario": 1,
                "aplica_a_todos": True,
                "pruebas_sugeridas": [prueba.id],
                "activo": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        tipo = TipoGestionMuestra.objects.get(nombre="Ingreso estandar")
        self.assertEqual(list(tipo.pruebas_sugeridas.values_list("id", flat=True)), [prueba.id])

    def test_predefined_test_batch_accepts_nested_detail_primary_keys(self):
        prueba = Prueba.objects.create(
            nombre_variable="Viscosidad lote",
            acronimo="VL",
            metodo=self.metodo,
            unidad_catalogo=self.unit,
            unidad_medida=self.unit.simbolo,
            condicion_catalogo=self.condition,
            condicion="40 °C",
        )

        response = self.client.post(
            "/api/technical-catalogs/predefined-test-batches/",
            {
                "nombre": "Plantilla aceite",
                "descripcion": "Base para aceite",
                "tipo_lote": "personalizado",
                "tipo_gestion": None,
                "es_default": False,
                "activo": True,
                "detalles": [
                    {
                        "prueba": prueba.id,
                        "equipo_prueba": self.metodo.equipo_prueba_id,
                        "metodo_equipo": self.metodo.id,
                        "condicion": self.condition.id,
                        "condicion_texto": "40 °C",
                        "unidad": "cSt",
                        "orden": 1,
                        "activo": True,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        batch = LotePruebasPredefinido.objects.get(nombre="Plantilla aceite")
        detail = batch.detalles.get()
        self.assertEqual(detail.prueba_id, prueba.id)
        self.assertEqual(detail.equipo_prueba_id, self.metodo.equipo_prueba_id)
        self.assertEqual(detail.metodo_equipo_id, self.metodo.id)
        self.assertEqual(detail.condicion_id, self.condition.id)

    def test_predefined_test_batch_preserves_structured_field_criteria(self):
        prueba = Prueba.objects.create(
            nombre_variable="Panel mixto",
            acronimo="PMIX",
            metodo=self.metodo,
            unidad_catalogo=self.unit,
            unidad_medida=self.unit.simbolo,
        )
        structured_criterion = {
            "campo_numerico": {
                "min_aceptable": "10",
                "max_aceptable": "20",
                "min_critico": "5",
                "max_critico": "25",
                "usar_amarillo": True,
            },
            "campo_booleano": {"valor_esperado": False},
        }

        response = self.client.post(
            "/api/technical-catalogs/predefined-test-batches/",
            {
                "nombre": "Plantilla mixta",
                "tipo_lote": "personalizado",
                "es_default": False,
                "activo": True,
                "detalles": [{
                    "prueba": prueba.id,
                    "criterio_limite_valor": structured_criterion,
                    "configuracion_resultados": {
                        "resultado_principal": {
                            "unidad": "cSt",
                            "condicion_texto": "Sin condición",
                        },
                    },
                    "orden": 1,
                    "activo": True,
                }],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        detail = LotePruebasPredefinido.objects.get(nombre="Plantilla mixta").detalles.get()
        self.assertEqual(detail.configuracion_resultados["resultado_principal"]["unidad"], "cSt")
        self.assertEqual(
            detail.criterio_limite_valor,
            '{"campo_numerico": {"min_aceptable": "10", "max_aceptable": "20", '
            '"min_critico": "5", "max_critico": "25", "usar_amarillo": true}, '
            '"campo_booleano": {"valor_esperado": false}}',
        )

    def test_predefined_batch_discards_redundant_top_scale_for_catalog_fields(self):
        prueba = Prueba.objects.create(
            nombre_variable="Panel ordinal por catalogo",
            acronimo="POC",
            metodo=self.metodo,
        )
        catalog = CatalogoTecnico.objects.create(
            nombre="Catalogo POC",
            codigo="catalogo_poc",
            tipo_muestra="aceite",
        )
        scale = EscalaComparacion.objects.create(
            nombre="Escala POC",
            codigo="escala_poc",
        )
        scale_item = EscalaComparacionItem.objects.create(
            escala=scale,
            etiqueta="Regular",
            valor_normalizado="regular",
            orden=1,
        )
        source = PruebaFuenteLimite.objects.create(
            prueba=prueba,
            tipo_limite="catalogo",
            catalogo_fuente=catalog,
        )
        field = PruebaLimiteCampo.objects.create(
            fuente_limite=source,
            nombre="Resultado ordinal",
            codigo="resultado_ordinal",
            tipo_comparacion="escala",
            escala_comparacion=scale,
        )

        response = self.client.post(
            "/api/technical-catalogs/predefined-test-batches/",
            {
                "nombre": "Plantilla ordinal por catalogo",
                "tipo_lote": "personalizado",
                "detalles": [{
                    "prueba": prueba.id,
                    "criterio_limite_escala": scale.id,
                    "criterio_limite_escala_item": scale_item.id,
                    "criterio_limite_valor": {
                        str(field.id): {"max_aceptable": "regular", "usar_amarillo": False},
                    },
                    "orden": 1,
                    "activo": True,
                }],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        detail = LotePruebasPredefinido.objects.get(nombre="Plantilla ordinal por catalogo").detalles.get()
        self.assertIsNone(detail.criterio_limite_escala_id)
        self.assertIsNone(detail.criterio_limite_escala_item_id)
        self.assertIn('"max_aceptable": "regular"', detail.criterio_limite_valor)
