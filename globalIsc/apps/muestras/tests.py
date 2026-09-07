from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoItem,
    CampoTecnicoMuestra,
    PruebaFuenteLimite,
    PruebaLimiteCampo,
    CriterioEvaluacionLimite,
)
from apps.misc.api.models.pruebas.index import (
    Prueba,
    PruebaResultado,
    PruebaResultadoComponente,
    PruebaResultadoDivision,
)
from apps.muestras.api.models.muestraAtributoTecnico.index import MuestraAtributoTecnico
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.serializers.loteMuestras.index import LoteMuestrasCreateSerializer
from apps.muestras.api.serializers.muestras.index import CreateMuestraSerializer
from apps.muestras.api.services.limit_engine import (
    resolve_and_evaluate_composite_result,
    resolve_and_evaluate_result,
)
from apps.muestras.api.models.sampleBatchExcel.index import SampleBatchExcelTemplateToken
from apps.muestras.api.views.sampleBatchExcel.index import (
    generate_template_workbook,
    parse_row,
    technical_fields_by_type,
    template_columns,
)
from apps.misc.api.views.dynamicTechnicalConfig.index import _build_limit_fields_from_prueba
from apps.users.api.models.index import User


class SampleLifecycleSafetyTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Empresa ciclo seguro")
        self.user = User.objects.create_superuser(
            email="lifecycle@example.com",
            password="test-password",
            empresa=self.empresa,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.lote = LoteMuestras.objects.create(
            tipo_cliente="registrado",
            cliente_empresa=self.empresa,
            fecha_envio=timezone.localdate(),
            estado="registrado",
            usuario_registro=self.user,
        )
        self.muestra = Muestra.objects.create(
            lote=self.lote,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )

    def test_non_empty_batch_cannot_be_physically_deleted(self):
        response = self.client.delete(f"/api/lubrication/sample-batches/{self.lote.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(LoteMuestras.objects.filter(pk=self.lote.pk).exists())
        self.assertTrue(Muestra.objects.filter(pk=self.muestra.pk).exists())

    def test_sample_invalidation_and_reactivation_keep_the_record(self):
        invalidated = self.client.post(
            f"/api/lubrication/samples/{self.muestra.id}/invalidate/",
            {"reason": "Identificación incorrecta"},
            format="json",
        )
        self.assertEqual(invalidated.status_code, 200)
        self.muestra.refresh_from_db()
        self.assertEqual(self.muestra.estado_operativo, "invalidada")
        self.assertEqual(self.muestra.motivo_invalidacion, "Identificación incorrecta")

        reactivated = self.client.post(
            f"/api/lubrication/samples/{self.muestra.id}/reactivate/",
            {"reason": "Identificación verificada"},
            format="json",
        )
        self.assertEqual(reactivated.status_code, 200)
        self.muestra.refresh_from_db()
        self.assertEqual(self.muestra.estado_operativo, "activa")
        self.assertTrue(Muestra.objects.filter(pk=self.muestra.pk).exists())


class SamplePartialUpdateTests(TestCase):
    def test_partial_metadata_update_does_not_require_resending_technical_attributes(self):
        empresa = Empresa.objects.create(nombre="Empresa edicion")
        user = User.objects.create_user(
            email="sample-edit@example.com",
            password="test-password",
            empresa=empresa,
        )
        sample = Muestra.objects.create(
            fecha_toma=timezone.now(),
            usuario_registro=user,
            tipo_muestra="aceite",
            observaciones="Antes",
        )

        serializer = CreateMuestraSerializer(
            sample,
            data={"observaciones": "Después"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        sample.refresh_from_db()
        self.assertEqual(sample.observaciones, "Después")


class DynamicLimitEngineTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(nombre="Global Oil Test")
        self.user = User.objects.create_user(
            email="limit-engine@example.com",
            password="test-password",
            empresa=empresa,
        )
        self.muestra = Muestra.objects.create(
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
            tipo_muestra="aceite",
        )
        self.prueba = Prueba.objects.create(
            nombre_variable="Viscosidad 100 C",
            acronimo="V100",
        )

    def test_catalog_limit_is_resolved_and_evaluated(self):
        catalogo = CatalogoTecnico.objects.create(
            nombre="Grado de viscosidad",
            codigo="grado_viscosidad",
            tipo_muestra="aceite",
        )
        item = CatalogoTecnicoItem.objects.create(
            catalogo=catalogo,
            nombre="SAE 70W-90",
        )
        MuestraAtributoTecnico.objects.create(
            muestra=self.muestra,
            catalogo=catalogo,
            item=item,
        )
        source = PruebaFuenteLimite.objects.create(
            prueba=self.prueba,
            catalogo_fuente=catalogo,
        )
        field = PruebaLimiteCampo.objects.create(
            fuente_limite=source,
            nombre="Viscosidad 100 C máxima",
            codigo="viscosidad_100_max",
            operador="max",
        )
        CriterioEvaluacionLimite.objects.create(
            fuente_limite=source,
            nombre=item.nombre,
            codigo=item.codigo,
            tipo_criterio="catalogo_item",
            catalogo_item=item,
            valores_limite={field.codigo: "18.5"},
        )

        resolved = resolve_and_evaluate_result("15.8", self.muestra, self.prueba)

        self.assertEqual(resolved.estado, "NORMAL")
        self.assertEqual(resolved.limit_value, "18.5")

    def test_unknown_attribute_returns_missing_information(self):
        catalogo = CatalogoTecnico.objects.create(
            nombre="Uso",
            codigo="uso",
            tipo_muestra="aceite",
        )
        MuestraAtributoTecnico.objects.create(
            muestra=self.muestra,
            catalogo=catalogo,
            desconocido=True,
        )
        source = PruebaFuenteLimite.objects.create(
            prueba=self.prueba,
            catalogo_fuente=catalogo,
        )
        PruebaLimiteCampo.objects.create(
            fuente_limite=source,
            nombre="Hierro máximo",
            codigo="hierro_maximo",
            operador="max",
        )

        resolved = resolve_and_evaluate_result("20", self.muestra, self.prueba)

        self.assertEqual(resolved.estado, "SIN_INFORMACION_TECNICA")

    def test_foam_generates_and_evaluates_six_component_limits(self):
        _, item, source = self._catalog_source("Nivel de desempeño", "nivel_desempeno", "API SN")
        values = []
        for sequence, components in [("I", ["FI", "EI"]), ("II", ["FII", "EII"]), ("III", ["FIII", "EIII"])]:
            result = PruebaResultado.objects.create(prueba=self.prueba, nombre=f"Secuencia {sequence}")
            division = PruebaResultadoDivision.objects.create(resultado=result, es_principal=True)
            for acronym in components:
                component = PruebaResultadoComponente.objects.create(
                    division=division,
                    nombre=acronym,
                    acronimo=acronym,
                )
                values.append((result, division, component))

        fields = _build_limit_fields_from_prueba(source, operador="max", unidad="ml")

        self.assertEqual(len(fields), 6)
        measurements = []
        criterion_values = {}
        for field, (result, division, component) in zip(fields, values):
            criterion_values[field.codigo] = "10"
            measurements.append({
                "resultado": result,
                "division": division,
                "componente": component,
                "valor": "9",
            })
        CriterioEvaluacionLimite.objects.create(
            fuente_limite=source,
            nombre=item.nombre,
            codigo=item.codigo,
            tipo_criterio="catalogo_item",
            catalogo_item=item,
            valores_limite=criterion_values,
        )

        resolved = resolve_and_evaluate_composite_result(measurements, self.muestra, self.prueba)

        self.assertEqual(resolved.estado, "NORMAL")
        self.assertEqual(resolved.evaluated_count, 6)

    def test_contamination_fails_when_any_component_exceeds_its_limit(self):
        _, item, source = self._catalog_source("Nivel de contaminación", "nivel_contaminacion", "ISO objetivo")
        result = PruebaResultado.objects.create(prueba=self.prueba, nombre="Conteo")
        division = PruebaResultadoDivision.objects.create(resultado=result, es_principal=True)
        values = []
        criterion_values = {}
        for acronym, limit, measured in [("4um", "10", "10"), ("6um", "12", "13"), ("10um", "20", "20")]:
            component = PruebaResultadoComponente.objects.create(
                division=division,
                nombre=acronym,
                acronimo=acronym,
            )
            field = PruebaLimiteCampo.objects.create(
                fuente_limite=source,
                nombre=acronym,
                codigo=acronym,
                operador="max",
                resultado=result,
                division=division,
                componente=component,
            )
            criterion_values[field.codigo] = limit
            values.append({
                "resultado": result,
                "division": division,
                "componente": component,
                "valor": measured,
            })
        CriterioEvaluacionLimite.objects.create(
            fuente_limite=source,
            nombre=item.nombre,
            codigo=item.codigo,
            tipo_criterio="catalogo_item",
            catalogo_item=item,
            valores_limite=criterion_values,
        )

        resolved = resolve_and_evaluate_composite_result(values, self.muestra, self.prueba)

        self.assertEqual(source.politica_evaluacion, "todas_deben_cumplir")
        self.assertEqual(resolved.estado, "CRITICO")
        self.assertEqual(resolved.passed_count, 2)

    def _catalog_source(self, name, code, item_name):
        catalog = CatalogoTecnico.objects.create(nombre=name, codigo=code, tipo_muestra="aceite")
        item = CatalogoTecnicoItem.objects.create(catalogo=catalog, nombre=item_name)
        MuestraAtributoTecnico.objects.create(muestra=self.muestra, catalogo=catalog, item=item)
        source = PruebaFuenteLimite.objects.create(prueba=self.prueba, catalogo_fuente=catalog)
        return catalog, item, source


class FixedSampleBatchExcelTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(nombre="Global Oil Excel Test")
        self.user = User.objects.create_user(
            email="excel-engine@example.com",
            password="test-password",
            empresa=empresa,
        )
        self.catalog = CatalogoTecnico.objects.create(
            nombre="Grado de viscosidad",
            codigo="grado_viscosidad",
            tipo_muestra="aceite",
            es_requerido_en_muestra=True,
            permite_desconocido=True,
        )
        self.item = CatalogoTecnicoItem.objects.create(
            catalogo=self.catalog,
            nombre="SAE 70W-90",
        )
        self.field = CampoTecnicoMuestra.objects.create(
            nombre_visible="Grado de viscosidad",
            codigo="grado_viscosidad",
            tipo_muestra="aceite",
            catalogo=self.catalog,
            visible_en_ingreso=True,
            orden=1,
            activo=True,
        )
        CatalogoTecnico.objects.create(
            nombre="Nivel de desempeno",
            codigo="nivel_desempeno",
            tipo_muestra="aceite",
            es_requerido_en_muestra=True,
            permite_desconocido=True,
        )
        CatalogoTecnico.objects.create(
            nombre="Uso",
            codigo="uso",
            tipo_muestra="aceite",
            es_requerido_en_muestra=True,
            permite_desconocido=True,
        )
        self.token = SampleBatchExcelTemplateToken.objects.create(
            requested_by=self.user,
            schema_version="sample-batch-v2",
            expires_at=timezone.now() + timedelta(hours=1),
        )

    def test_template_adds_fixed_oil_catalog_column(self):
        workbook = generate_template_workbook(self.token)
        headers = [cell.value for cell in workbook["Aceites"][1]]

        self.assertIn("Grado de viscosidad", headers)

    def test_fixed_catalog_value_is_parsed_as_sample_attribute(self):
        workbook = generate_template_workbook(self.token)
        ws = workbook["Aceites"]
        columns = template_columns("aceite")
        index = {key: position for position, (key, _) in enumerate(columns, start=1)}
        ws.cell(2, index["fecha_toma"], timezone.now())
        ws.cell(2, index["condicion"], "nueva")
        ws.cell(2, index["referencia_marca"], "Referencia de prueba")
        ws.cell(2, index[f"tecnico_{self.field.id}"], f"{self.item.id} | SAE 70W-90")

        data, errors = parse_row(ws, 2, "aceite", technical_fields_by_type())

        self.assertEqual(errors, [])
        self.assertEqual(
            data["atributos_tecnicos"][str(self.catalog.id)],
            {
                "item": str(self.item.id),
                "desconocido": False,
                "campo_tecnico_muestra": str(self.field.id),
            },
        )


class LoteMuestrasCreateSerializerTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Global Oil Lote Test")
        self.user = User.objects.create_user(
            email="lote-create@example.com",
            password="test-password",
            empresa=self.empresa,
        )

    def test_nested_sample_accepts_technical_attributes_without_sample_id(self):
        catalog_1, item_1 = self._catalog_item("Grado de viscosidad", "grado_viscosidad")
        catalog_2, item_2 = self._catalog_item("Nivel de desempeno", "nivel_desempeno")
        catalog_3, item_3 = self._catalog_item("Uso", "uso")
        payload = {
            "tipo_cliente": "registrado",
            "cliente_empresa": self.empresa.id,
            "contacto_nombre": "GLOBAL OIL CONTADOR",
            "contacto_telefono": "3222341090",
            "contacto_email": "globaloilSA@gmail.com",
            "fecha_envio": "2026-06-03",
            "fecha_recepcion": "2026-06-18",
            "estado": "registrado",
            "usuario_registro": self.user.id,
            "muestras": [
                {
                    "fecha_toma": "2026-06-18T10:05:00-05:00",
                    "tipo_muestra": "aceite",
                    "condicion": "usada",
                    "referencia_equipo": None,
                    "equipo_placa": "ewtdasds",
                    "periodo_servicio_aceite": 22,
                    "unidad_periodo_aceite": "horas",
                    "periodo_servicio_equipo": 323,
                    "unidad_periodo_equipo": "horas",
                    "referencia_marca": "MOBILGEAR X500",
                    "campos_adicionales": {"fabricante": "mobil"},
                    "atributos_tecnicos": [
                        {"catalogo": catalog_1.id, "item": item_1.id, "desconocido": False},
                        {"catalogo": catalog_2.id, "item": item_2.id, "desconocido": False},
                        {"catalogo": catalog_3.id, "item": item_3.id, "desconocido": False},
                    ],
                }
            ],
        }

        serializer = LoteMuestrasCreateSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_mixed_batch_ignores_legacy_oil_catalog_field_for_grease(self):
        catalog, item = self._catalog_item("Grado de viscosidad", "grado_viscosidad_mixto")
        field = CampoTecnicoMuestra.objects.create(
            nombre_visible="Campo legado ambiguo",
            codigo="campo_legado_ambiguo",
            tipo_muestra="ambos",
            catalogo=catalog,
            obligatorio=True,
            visible_en_ingreso=True,
        )
        payload = {
            "tipo_cliente": "ocasional",
            "cliente_ocasional_nombre": "Taller el rápido",
            "contacto_nombre": "Javier",
            "fecha_envio": "2026-08-04",
            "estado": "registrado",
            "usuario_registro": self.user.id,
            "muestras": [
                {
                    "fecha_toma": "2026-08-05T19:37:00-05:00",
                    "tipo_muestra": "aceite",
                    "condicion": "nueva",
                    "referencia_marca": "Aceite nuevo",
                    "atributos_tecnicos": [{
                        "campo_tecnico": field.id,
                        "catalogo": catalog.id,
                        "item": item.id,
                        "desconocido": False,
                    }],
                },
                {
                    "fecha_toma": "2026-08-05T19:38:00-05:00",
                    "tipo_muestra": "grasa",
                    "condicion": "usada",
                    "equipo_placa": "EQ-GRASA",
                    "referencia_marca": "Grasa usada",
                    "atributos_tecnicos": [],
                },
            ],
        }

        serializer = LoteMuestrasCreateSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def _catalog_item(self, name, code):
        catalog = CatalogoTecnico.objects.create(
            nombre=name,
            codigo=code,
            tipo_muestra="aceite",
            es_requerido_en_muestra=True,
        )
        item = CatalogoTecnicoItem.objects.create(
            catalogo=catalog,
            nombre=f"{name} item",
        )
        return catalog, item
