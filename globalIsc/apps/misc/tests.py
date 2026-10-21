from io import BytesIO, StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import F
from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook
from rest_framework.test import APIClient

from apps.activesTree.api.models.index import Carpeta, Lubricante, PuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoVersion,
    CatalogoTecnicoItem,
    CampoTecnicoMuestra,
    EscalaComparacion,
    EscalaComparacionItem,
    PruebaFuenteLimite,
    PruebaLimiteCampo,
    CriterioEvaluacionLimite,
)
from apps.misc.api.models.lotesPruebasPredefinidos.index import LotePruebasPredefinido
from apps.misc.api.models.pruebas.index import Prueba, PruebaResultado, PruebaResultadoDivision, PruebaResultadoComponente
from apps.misc.api.models.technicalCatalogs.index import CategoriaUnidad, Condicion, EquipoPrueba, MetodoEquipo, Unidad
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
        self.assertEqual(
            set(CategoriaUnidad.objects.values_list("nombre", flat=True)),
            {"Viscosidad", "Concentración", "Conteo", "Temperatura", "Espuma", "Adimensional"},
        )
        self.assertEqual(Unidad.objects.filter(categoria__isnull=True).count(), 0)
        self.assertEqual(
            Unidad.objects.filter(magnitud__isnull=False)
            .exclude(magnitud=F("categoria__nombre"))
            .count(),
            0,
        )
        self.assertEqual(
            Condicion.objects.exclude(magnitud_categoria=F("unidad__categoria")).count(),
            0,
        )
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

    def test_command_removes_assets_before_machines(self):
        empresa = Empresa.objects.create(nombre="Empresa con activos previos")
        maquina = Maquina.objects.create(nombre="Máquina previa", empresa=empresa)
        lubricante = Lubricante.objects.create(
            nombre="Lubricante previo",
            fabricante="Global Oil",
            referencia="PREVIO-1",
        )
        PuntoMuestreo.objects.create(
            maquina=maquina,
            nombre="Punto previo",
            lubricante_catalogo=lubricante,
        )
        Carpeta.objects.create(
            nombre="Carpeta previa",
            compania=empresa,
            typeFolder="maquina",
            machine=maquina,
        )

        call_command("reset_globaloil_flow", "--yes", stdout=StringIO())

        self.assertFalse(Maquina.objects.exists())
        self.assertFalse(PuntoMuestreo.objects.exists())
        self.assertFalse(Carpeta.objects.exists())
        self.assertFalse(Lubricante.objects.exists())


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

    def test_matrix_import_preserves_every_supported_operator(self):
        test = Prueba.objects.create(nombre_variable="Matriz de operaciones", acronimo="MOP")
        source = PruebaFuenteLimite.objects.create(
            prueba=test,
            configuracion_regla={
                "campos": [{
                    "codigo": "resultado",
                    "nombre": "Resultado",
                    "origen_limite": "catalogo",
                    "tipo_comparacion": "numerica",
                }],
            },
        )
        rows = [
            ("max", "NO", None, None, "10", None, None),
            ("min", "NO", None, "10", None, None, None),
            ("between", "NO", None, "10", "20", None, None),
            ("eq", "SI", None, None, None, None, "10"),
            ("neq", "SI", None, None, None, None, "10"),
            ("in", "SI", None, None, None, None, "10;20"),
            ("not_in", "SI", None, None, None, None, "10;20"),
            ("informativo", "SI", None, None, None, None, None),
        ]
        criteria = {}
        for index, (operator, *_values) in enumerate(rows, start=1):
            criteria[operator] = CriterioEvaluacionLimite.objects.create(
                fuente_limite=source,
                nombre=f"Criterio {operator}",
                codigo=f"criterio_{index}",
            )

        workbook = Workbook()
        sheet = workbook.active
        sheet.append([
            "criterio_codigo", "campo_codigo", "operacion", "usa_semaforo",
            "min_critico", "min_aceptable", "max_aceptable", "max_critico",
            "valor_objetivo", "valores_permitidos", "comentario",
        ])
        for criterion, (operator, yellow, min_critical, min_ok, max_ok, max_critical, expected) in zip(criteria.values(), rows):
            sheet.append([
                criterion.codigo, "resultado", operator, yellow,
                min_critical, min_ok, max_ok, max_critical, expected, None, None,
            ])
        stream = BytesIO()
        workbook.save(stream)
        upload = SimpleUploadedFile(
            "matriz.xlsx",
            stream.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response = self.client.post(
            f"/api/technical-config/limit-sources/{source.id}/import-matrix/",
            {"archivo": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["actualizados"], len(rows))
        for operator, criterion in criteria.items():
            criterion.refresh_from_db()
            rule = criterion.valores_limite["resultado"]
            self.assertEqual(rule["operador"], operator)
            self.assertFalse(rule["usar_amarillo"])
        self.assertEqual(criteria["eq"].valores_limite["resultado"]["valor_esperado"], "10")
        self.assertEqual(criteria["in"].valores_limite["resultado"]["valor_esperado"], "10;20")

    def test_catalog_version_selection_and_deactivation_never_deactivate_the_catalog(self):
        catalog = CatalogoTecnico.objects.create(nombre="Viscosidad", codigo="viscosidad")
        first = CatalogoTecnicoVersion.objects.create(catalogo=catalog, numero=1, nombre="Inicial")
        second = CatalogoTecnicoVersion.objects.create(catalogo=catalog, numero=2, nombre="Nueva")
        catalog.version_actual = first
        catalog.save(update_fields=["version_actual"])

        selected = self.client.post(f"/api/technical-config/catalog-versions/{second.id}/make-current/")
        self.assertEqual(selected.status_code, 200)
        catalog.refresh_from_db()
        self.assertEqual(catalog.version_actual_id, second.id)
        self.assertTrue(catalog.activo)

        deactivated = self.client.post(f"/api/technical-config/catalog-versions/{first.id}/deactivate/")
        self.assertEqual(deactivated.status_code, 200)
        first.refresh_from_db()
        catalog.refresh_from_db()
        self.assertFalse(first.activo)
        self.assertTrue(catalog.activo)
        self.assertEqual(catalog.version_actual_id, second.id)

        blocked = self.client.post(f"/api/technical-config/catalog-versions/{second.id}/deactivate/")
        self.assertEqual(blocked.status_code, 400)
        second.refresh_from_db()
        self.assertTrue(second.activo)

    def test_inactive_catalog_is_excluded_from_sample_form_without_erasing_its_configuration(self):
        catalog = CatalogoTecnico.objects.create(
            nombre="Uso de aceite",
            codigo="uso_aceite",
            tipo_muestra="aceite",
        )
        CampoTecnicoMuestra.objects.create(
            nombre_visible="Uso",
            codigo="uso",
            tipo_muestra="aceite",
            catalogo=catalog,
            visible_en_ingreso=True,
        )

        active_response = self.client.get("/api/technical-config/catalogs/sample-form/?tipo_muestra=aceite")
        self.assertEqual(active_response.status_code, 200)
        self.assertTrue(any(field["catalogo"] == catalog.id for field in active_response.data))

        catalog.soft_delete()
        inactive_response = self.client.get("/api/technical-config/catalogs/sample-form/?tipo_muestra=aceite")
        self.assertEqual(inactive_response.status_code, 200)
        self.assertFalse(any(field["catalogo"] == catalog.id for field in inactive_response.data))
        self.assertTrue(CatalogoTecnico.objects.filter(pk=catalog.id).exists())

    def test_sample_form_exposes_only_current_catalog_version_items(self):
        catalog = CatalogoTecnico.objects.create(
            nombre="Grado de viscosidad", codigo="grado_viscosidad", tipo_muestra="aceite",
        )
        previous = CatalogoTecnicoVersion.objects.create(catalogo=catalog, numero=1, nombre="Inicial")
        current = CatalogoTecnicoVersion.objects.create(catalogo=catalog, numero=2, nombre="Vigente")
        catalog.version_actual = current
        catalog.save(update_fields=["version_actual"])
        CatalogoTecnicoItem.objects.create(catalogo=catalog, version=previous, nombre="SAE 20W-60", codigo="sae_20w_60")
        CatalogoTecnicoItem.objects.create(catalogo=catalog, version=current, nombre="SAE 20W-60", codigo="sae_20w_60")
        CatalogoTecnicoItem.objects.create(catalogo=catalog, version=current, nombre="SAE 15W-40", codigo="sae_15w_40")
        CampoTecnicoMuestra.objects.create(
            nombre_visible="Grado de viscosidad", codigo="grado_viscosidad",
            tipo_muestra="aceite", catalogo=catalog, visible_en_ingreso=True,
        )

        response = self.client.get("/api/technical-config/catalogs/sample-form/?tipo_muestra=aceite")

        self.assertEqual(response.status_code, 200)
        field = next(item for item in response.data if item["catalogo"] == catalog.id)
        self.assertEqual([item["codigo"] for item in field["catalogo_info"]["items"]], ["sae_15w_40", "sae_20w_60"])

    def test_sample_field_rejects_catalog_with_incompatible_sample_kind(self):
        oil_catalog = CatalogoTecnico.objects.create(
            nombre="Viscosidad de aceite",
            codigo="viscosidad_aceite",
            tipo_muestra="aceite",
        )
        rejected = self.client.post(
            "/api/technical-config/sample-fields/",
            {
                "nombre_visible": "NLGI",
                "codigo": "nlgi",
                "tipo_muestra": "grasa",
                "catalogo": oil_catalog.id,
                "activo": True,
                "visible_en_ingreso": True,
                "visible_en_asignacion": True,
            },
            format="json",
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("catalogo", rejected.data)

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

    def test_global_company_is_hidden_from_operational_company_lists_unless_requested(self):
        internal, _ = Empresa.objects.get_or_create(
            nit="GLOBAL-OIL-INTERNAL",
            defaults={"nombre": "Global Oil", "is_internal": True},
        )
        internal.is_internal = True
        internal.save(update_fields=["is_internal"])

        response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn(internal.id, [item["id"] for item in response.data])

        response = self.client.get("/api/companies/?include_internal=true")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(internal.id, [item["id"] for item in response.data])

    def test_global_company_cannot_be_disabled(self):
        internal, _ = Empresa.objects.get_or_create(
            nit="GLOBAL-OIL-INTERNAL",
            defaults={"nombre": "Global Oil", "is_internal": True},
        )
        internal.is_internal = True
        internal.save(update_fields=["is_internal"])

        response = self.client.delete(f"/api/companies/{internal.id}/")
        self.assertEqual(response.status_code, 400, response.data)
        internal.refresh_from_db()
        self.assertTrue(internal.is_active)

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

    @patch("apps.users.api.services.send_invitation_email", return_value=True)
    def test_global_can_create_company_and_explicitly_reinvite_existing_admin(self, _send_mail):
        existing = User.objects.create_user(
            email="admin-existente@example.com",
            password="test-password",
            empresa=self.empresa,
            role=User.Role.EMPRESA,
        )

        response = self.client.post(
            "/api/companies/",
            {
                "nombre": "Empresa destino",
                "nit": "900005",
                "admin_email": existing.email,
                "transfer_existing_admin": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        destination = Empresa.objects.get(nombre="Empresa destino")
        existing.refresh_from_db()
        self.assertEqual(existing.empresa_id, self.empresa.id)
        invitation = UserInvitation.objects.get(pk=response.data["admin_invitation"]["id"])
        self.assertEqual(invitation.metadata["company_transfer"]["to_company_id"], destination.id)


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


class UnitCategoryApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="unit-categories@example.com",
            password="test-password",
            role=User.Role.GLOBAL,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_category_is_unique_and_units_use_the_managed_category(self):
        created = self.client.post(
            "/api/technical-catalogs/unit-categories/",
            {"nombre": "Temperatura QA aislada", "descripcion": "Magnitudes térmicas"},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        category_id = created.data["id"]

        duplicate = self.client.post(
            "/api/technical-catalogs/unit-categories/",
            {"nombre": "  tEMPERATURA qa AISLADA  "},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400, duplicate.data)
        self.assertIn("nombre", duplicate.data)

        unit = self.client.post(
            "/api/technical-catalogs/units/",
            {"nombre": "Grados Celsius", "simbolo": "°C QA", "categoria": category_id},
            format="json",
        )
        self.assertEqual(unit.status_code, 201, unit.data)
        self.assertEqual(unit.data["categoria"], category_id)
        self.assertEqual(unit.data["categoria_info"]["nombre"], "Temperatura QA aislada")
        self.assertEqual(unit.data["magnitud"], "Temperatura QA aislada")

        renamed = self.client.patch(
            f"/api/technical-catalogs/unit-categories/{category_id}/",
            {"nombre": "Temperatura de proceso"},
            format="json",
        )
        self.assertEqual(renamed.status_code, 200, renamed.data)
        self.assertEqual(Unidad.objects.get(pk=unit.data["id"]).magnitud, "Temperatura de proceso")

        condition = self.client.post(
            "/api/technical-catalogs/conditions/",
            {
                "nombre": "Temperatura de referencia QA",
                "magnitud_categoria": category_id,
                "valor": 40,
                "unidad": unit.data["id"],
            },
            format="json",
        )
        self.assertEqual(condition.status_code, 201, condition.data)
        self.assertEqual(condition.data["magnitud"], "Temperatura de proceso")
        self.assertEqual(condition.data["magnitud_info"]["id"], category_id)

        other_category = self.client.post(
            "/api/technical-catalogs/unit-categories/",
            {"nombre": "Presión QA aislada"},
            format="json",
        )
        self.assertEqual(other_category.status_code, 201, other_category.data)
        invalid_condition = self.client.post(
            "/api/technical-catalogs/conditions/",
            {
                "nombre": "Condición incompatible QA",
                "magnitud_categoria": other_category.data["id"],
                "valor": 40,
                "unidad": unit.data["id"],
            },
            format="json",
        )
        self.assertEqual(invalid_condition.status_code, 400, invalid_condition.data)
        self.assertIn("unidad", invalid_condition.data)

        protected = self.client.delete(f"/api/technical-catalogs/unit-categories/{category_id}/")
        self.assertEqual(protected.status_code, 409, protected.data)
        self.assertTrue(CategoriaUnidad.objects.get(pk=category_id).activo)

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
