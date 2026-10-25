from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APIRequestFactory

from backend.api_exceptions import api_exception_handler

from apps.misc.api.models.companies.index import Empresa
from apps.activesTree.api.models.machines.index import Maquina
from apps.activesTree.api.models.index import AsignacionPuntoMuestreo, Carpeta, Lubricante, PuntoMuestreo
from apps.misc.api.models.tipoGestionMuestra.index import TipoGestionMuestra
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoItem,
    CatalogoTecnicoVersion,
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
from apps.muestras.api.models.auditoria import EventoAuditoriaOperativa
from apps.muestras.api.serializers.loteMuestras.index import LoteMuestraWorkspaceSerializer, LoteMuestrasCreateSerializer
from apps.muestras.api.serializers.muestras.index import CreateMuestraSerializer
from apps.muestras.services.operational_audit import record_operational_event
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
from apps.dashboard.api.services.operational_center import due_info_for_batch
from apps.misc.api.views.dynamicTechnicalConfig.index import _build_limit_fields_from_prueba
from apps.users.api.models.index import (
    SecurityPermission,
    SecurityRole,
    SecurityRolePermission,
    User,
    UserCompanyProfile,
)


class ApiExceptionContractTests(SimpleTestCase):
    def test_validation_error_keeps_legacy_fields_and_adds_canonical_metadata(self):
        request = APIRequestFactory().post("/api/lubrication/sample-batches/")
        response = api_exception_handler(
            ValidationError({"muestras": [{"punto_muestreo": ["Seleccione un punto."]}]}),
            {"request": request},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["muestras"][0]["punto_muestreo"][0], "Seleccione un punto.")
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertEqual(response.data["error"]["message"], "Seleccione un punto.")
        self.assertEqual(response.data["error"]["fields"]["muestras"][0]["punto_muestreo"][0], "Seleccione un punto.")


class LoteMuestraWorkspaceSerializerTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Empresa tablero lotes")
        self.user = User.objects.create_user(
            email="workspace-lotes@example.com",
            password="test-password",
            empresa=self.empresa,
        )
        self.tipo_gestion = TipoGestionMuestra.objects.create(
            nombre="Diagnóstico prioritario",
            dias_habiles=3,
        )
        self.lote = LoteMuestras.objects.create(
            tipo_cliente="registrado",
            cliente_empresa=self.empresa,
            contacto_nombre="Contacto",
            fecha_envio=timezone.localdate(),
            fecha_recepcion=timezone.localdate(),
            tipo_gestion=self.tipo_gestion,
            usuario_registro=self.user,
        )
        self.machine = Maquina.objects.create(empresa=self.empresa, nombre="Bomba principal", codigo_equipo="BP-01")
        self.point = PuntoMuestreo.objects.create(maquina=self.machine, nombre="Reductor")

    def test_workspace_row_keeps_its_own_asset_context_and_management_deadline(self):
        sample = Muestra.objects.create(
            lote=self.lote,
            fecha_toma=timezone.now(),
            tipo_muestra="aceite",
            condicion="usada",
            referencia_equipo=self.machine,
            usuario_registro=self.user,
        )
        AsignacionPuntoMuestreo.objects.create(
            muestra=sample,
            punto_muestreo=self.point,
            origen="lote",
            asignado_por=self.user,
        )

        data = LoteMuestraWorkspaceSerializer(sample).data

        self.assertEqual(data["equipo"]["label"], "BP-01")
        self.assertEqual(data["punto_muestreo"]["nombre"], "Reductor")
        self.assertTrue(data["plazo_entrega"]["configured"])
        self.assertEqual(data["plazo_entrega"]["basis"], "habiles")
        self.assertEqual(data["plazo_entrega"]["total_days"], 3)

    def test_deadline_starts_only_after_laboratory_reception(self):
        self.lote.fecha_recepcion = None
        self.lote.save(update_fields=["fecha_recepcion"])
        sample = Muestra.objects.create(
            lote=self.lote,
            fecha_toma=timezone.now(),
            tipo_muestra="aceite",
            condicion="usada",
            usuario_registro=self.user,
        )

        workspace_deadline = LoteMuestraWorkspaceSerializer(sample).data["plazo_entrega"]
        dashboard_deadline = due_info_for_batch(self.lote, today=timezone.localdate())

        self.assertTrue(workspace_deadline["configured"])
        self.assertTrue(workspace_deadline["waiting_reception"])
        self.assertIsNone(workspace_deadline["due_date"])
        self.assertEqual(workspace_deadline["label"], "SLA inicia al recibir en laboratorio")
        self.assertEqual(dashboard_deadline["urgency"], "pendiente_recepcion")
        self.assertIsNone(dashboard_deadline["due_date"])


class SampleIdentifierTests(TestCase):
    def setUp(self):
        self.company = Empresa.objects.create(nombre="Empresa consecutivos")
        self.user = User.objects.create_superuser(
            email="identifiers@example.com",
            password="test-password",
            empresa=self.company,
        )
        self.batch = LoteMuestras.objects.create(
            tipo_cliente="registrado",
            cliente_empresa=self.company,
            fecha_envio=timezone.localdate(),
            estado="registrado",
            usuario_registro=self.user,
        )

    def test_new_sample_uses_next_yearly_identifier_even_for_same_context(self):
        prefix = f"M{timezone.now().year}"
        Muestra.objects.create(
            id=f"{prefix}0227",
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )

        following = Muestra.objects.create(
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )

        self.assertEqual(following.id, f"{prefix}0228")


class OperationalAuditTests(TestCase):
    def setUp(self):
        self.company = Empresa.objects.create(nombre="Empresa auditoría operacional")
        self.user = User.objects.create_superuser(
            email="audit-operator@example.com",
            password="test-password",
            empresa=self.company,
        )
        self.batch = LoteMuestras.objects.create(
            tipo_cliente="registrado",
            cliente_empresa=self.company,
            fecha_envio=timezone.localdate(),
            estado="registrado",
            usuario_registro=self.user,
        )
        self.sample = Muestra.objects.create(
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )

    def test_event_inherits_lot_and_company_from_sample(self):
        event = record_operational_event(
            actor=self.user,
            action="muestra.actualizada",
            entity_type="muestra",
            entity_id=self.sample.id,
            muestra=self.sample,
            before={"condicion": "usada"},
            after={"condicion": "nueva"},
        )

        self.assertEqual(event.lote_id, self.batch.id)
        self.assertEqual(event.empresa_id, self.company.id)
        self.assertEqual(event.muestra_id, self.sample.id)
        self.assertEqual(event.estado_anterior["condicion"], "usada")
        self.assertEqual(event.estado_nuevo["condicion"], "nueva")
        self.assertEqual(EventoAuditoriaOperativa.objects.count(), 1)


class BatchObjectAuthorizationTests(TestCase):
    """Regression coverage for BOLA/IDOR in the sample-batch flow."""

    def setUp(self):
        self.company_a = Empresa.objects.create(nombre="Empresa A - acceso")
        self.company_b = Empresa.objects.create(nombre="Empresa B - protegida")
        self.user = User.objects.create_user(
            email="operator-a@example.com",
            password="test-password",
            empresa=self.company_a,
            role=User.Role.EMPRESA,
            is_active=True,
            access_status=User.AccessStatus.ACTIVE,
        )
        role = SecurityRole.objects.create(
            name="Operador de pruebas de aislamiento",
            code="operator-object-access-tests",
            scope=SecurityRole.Scope.COMPANY,
        )
        for code in ["lotes.ver", "laboratorio.ingresar_lote"]:
            permission, _ = SecurityPermission.objects.get_or_create(
                code=code,
                defaults={"module": code.split(".")[0], "action": code.split(".")[1]},
            )
            SecurityRolePermission.objects.create(role=role, permission=permission, allowed=True)
        UserCompanyProfile.objects.create(
            user=self.user,
            empresa=self.company_a,
            role=role,
            status=UserCompanyProfile.Status.ACTIVE,
        )
        self.foreign_lote = LoteMuestras.objects.create(
            id="L-FOREIGN-ACCESS",
            tipo_cliente="registrado",
            cliente_empresa=self.company_b,
            fecha_envio=timezone.localdate(),
            estado="registrado",
            usuario_registro=self.user,
        )
        Muestra.objects.create(
            lote=self.foreign_lote,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_company_user_cannot_retrieve_a_foreign_batch_by_id(self):
        response = self.client.get(f"/api/lubrication/sample-batches/{self.foreign_lote.id}/")

        self.assertEqual(response.status_code, 404)

    def test_company_user_cannot_create_lab_entry_for_foreign_batch(self):
        response = self.client.post(
            "/api/lubrication/lab-batch-entries/",
            {"lote": self.foreign_lote.id, "fecha_recepcion": timezone.now().isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("No tiene acceso", str(response.data))


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
        self.empresa = Empresa.objects.create(nombre="Global Oil Excel Test")
        self.user = User.objects.create_user(
            email="excel-engine@example.com",
            password="test-password",
            empresa=self.empresa,
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

    def test_template_uses_only_the_current_catalog_edition(self):
        old_version = CatalogoTecnicoVersion.objects.create(catalogo=self.catalog, numero=1, nombre="Edición anterior")
        current_version = CatalogoTecnicoVersion.objects.create(catalogo=self.catalog, numero=2, nombre="Edición vigente")
        self.catalog.version_actual = current_version
        self.catalog.save(update_fields=["version_actual"])
        self.item.version = current_version
        self.item.save(update_fields=["version"])
        historical_duplicate = CatalogoTecnicoItem.objects.create(
            catalogo=self.catalog,
            version=old_version,
            nombre=self.item.nombre,
            codigo="sae_70w_90_historico",
        )

        workbook = generate_template_workbook(self.token)
        catalog_ws = workbook["_CATALOGOS"]
        headers = {cell.value: cell.column for cell in catalog_ws[1]}
        values = [value for value in catalog_ws.iter_cols(
            min_col=headers[f"tecnico_{self.field.id}"],
            max_col=headers[f"tecnico_{self.field.id}"],
            min_row=2,
            values_only=True,
        ).__next__() if value]

        self.assertIn(f"{self.item.id} | {self.item.nombre}", values)
        self.assertNotIn(f"{historical_duplicate.id} | {historical_duplicate.nombre}", values)

    def test_template_offers_registered_lubricants_and_uses_their_identity(self):
        lubricant = Lubricante.objects.create(
            nombre="Aceite hidráulico 68",
            fabricante="Mobil",
            referencia="DTE 25 Ultra",
        )
        workbook = generate_template_workbook(self.token)
        ws = workbook["Aceites"]
        columns = template_columns("aceite")
        index = {key: position for position, (key, _) in enumerate(columns, start=1)}

        self.assertIn("Lubricante registrado", [cell.value for cell in ws[1]])
        catalog_ws = workbook["_CATALOGOS"]
        catalog_headers = {cell.value: cell.column for cell in catalog_ws[1]}
        lubricant_values = [value for value in catalog_ws.iter_cols(
            min_col=catalog_headers["Lubricantes"],
            max_col=catalog_headers["Lubricantes"],
            min_row=2,
            values_only=True,
        ).__next__() if value]
        self.assertIn(f"{lubricant.id} | Mobil · DTE 25 Ultra", lubricant_values)

        ws.cell(2, index["fecha_toma"], timezone.now())
        ws.cell(2, index["condicion"], "nueva")
        ws.cell(2, index["lubricante_catalogo"], f"{lubricant.id} | Mobil · DTE 25 Ultra")
        ws.cell(2, index[f"tecnico_{self.field.id}"], f"{self.item.id} | {self.item.nombre}")

        data, errors = parse_row(ws, 2, "aceite", technical_fields_by_type())

        self.assertEqual(errors, [])
        self.assertEqual(data["lubricante_catalogo"], str(lubricant.id))
        self.assertEqual(data["fabricante"], "Mobil")
        self.assertEqual(data["referencia_marca"], "DTE 25 Ultra")

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
            data["atributos_tecnicos"][str(self.field.id)],
            {
                "item": str(self.item.id),
                "desconocido": False,
                "campo_tecnico_muestra": str(self.field.id),
            },
        )

    def test_excel_keeps_distinct_values_for_fields_that_share_a_catalog(self):
        secondary_item = CatalogoTecnicoItem.objects.create(
            catalogo=self.catalog,
            nombre="SAE 10W-60",
        )
        shared_catalog_field = CampoTecnicoMuestra.objects.create(
            nombre_visible="Campo grasa",
            codigo="campo_grasa",
            tipo_muestra="ambos",
            catalogo=self.catalog,
            visible_en_ingreso=True,
            obligatorio=True,
            orden=2,
        )
        workbook = generate_template_workbook(self.token)
        ws = workbook["Aceites"]
        columns = template_columns("aceite")
        index = {key: position for position, (key, _) in enumerate(columns, start=1)}
        ws.cell(2, index["fecha_toma"], timezone.now())
        ws.cell(2, index["condicion"], "nueva")
        ws.cell(2, index["referencia_marca"], "Referencia de prueba")
        ws.cell(2, index[f"tecnico_{self.field.id}"], f"{self.item.id} | {self.item.nombre}")
        ws.cell(
            2,
            index[f"tecnico_{shared_catalog_field.id}"],
            f"{secondary_item.id} | {secondary_item.nombre}",
        )

        data, errors = parse_row(ws, 2, "aceite", technical_fields_by_type())

        self.assertEqual(errors, [])
        self.assertEqual(
            data["atributos_tecnicos"][str(self.field.id)]["item"],
            str(self.item.id),
        )
        self.assertEqual(
            data["atributos_tecnicos"][str(shared_catalog_field.id)]["item"],
            str(secondary_item.id),
        )

    def test_unknown_is_accepted_for_every_technical_field(self):
        self.field.permite_desconocido = False
        self.field.obligatorio = True
        self.field.save(update_fields=["permite_desconocido", "obligatorio"])
        self.catalog.permite_desconocido = False
        self.catalog.save(update_fields=["permite_desconocido"])
        workbook = generate_template_workbook(self.token)
        ws = workbook["Aceites"]
        columns = template_columns("aceite")
        index = {key: position for position, (key, _) in enumerate(columns, start=1)}
        ws.cell(2, index["fecha_toma"], timezone.now())
        ws.cell(2, index["condicion"], "nueva")
        ws.cell(2, index["referencia_marca"], "Referencia de prueba")
        ws.cell(2, index[f"tecnico_{self.field.id}"], "DESCONOCIDO")

        data, errors = parse_row(ws, 2, "aceite", technical_fields_by_type())

        self.assertEqual(errors, [])
        self.assertTrue(data["atributos_tecnicos"][str(self.field.id)]["desconocido"])

    def test_preview_row_includes_human_readable_machine_and_sampling_point(self):
        machine = Maquina.objects.create(nombre="Equipo de prueba", empresa=self.empresa)
        point = PuntoMuestreo.objects.create(maquina=machine, nombre="Reductor principal")
        workbook = generate_template_workbook(self.token)
        ws = workbook["Aceites"]
        columns = template_columns("aceite")
        index = {key: position for position, (key, _) in enumerate(columns, start=1)}
        ws.cell(2, index["fecha_toma"], timezone.now())
        ws.cell(2, index["condicion"], "usada")
        ws.cell(2, index["referencia_marca"], "Referencia de prueba")
        ws.cell(2, index["punto_muestreo"], f"{point.id} | {machine.nombre} | {point.nombre}")
        ws.cell(2, index[f"tecnico_{self.field.id}"], f"{self.item.id} | SAE 70W-90")

        data, errors = parse_row(ws, 2, "aceite", technical_fields_by_type())

        self.assertEqual(errors, [])
        self.assertEqual(data["referencia_equipo"], str(machine.id))
        self.assertEqual(data["referencia_equipo_nombre"], machine.nombre)
        self.assertEqual(data["punto_muestreo"], str(point.id))
        self.assertEqual(data["punto_muestreo_nombre"], point.nombre)

    def test_preview_accepts_manual_machine_and_manual_sampling_point(self):
        workbook = generate_template_workbook(self.token)
        ws = workbook["Aceites"]
        columns = template_columns("aceite")
        index = {key: position for position, (key, _) in enumerate(columns, start=1)}
        ws.cell(2, index["fecha_toma"], timezone.now())
        ws.cell(2, index["condicion"], "usada")
        ws.cell(2, index["referencia_marca"], "Referencia de prueba")
        ws.cell(2, index["equipo_placa"], "TALLER-MANUAL-01")
        ws.cell(2, index["punto_muestreo_manual"], "Reductor lado motor")
        ws.cell(2, index[f"tecnico_{self.field.id}"], f"{self.item.id} | SAE 70W-90")

        data, errors = parse_row(ws, 2, "aceite", technical_fields_by_type(), empresa_id=self.empresa.pk)

        self.assertEqual(errors, [])
        self.assertEqual(data["equipo_placa"], "TALLER-MANUAL-01")
        self.assertEqual(data["punto_muestreo_manual"], "Reductor lado motor")

    def test_template_assets_are_scoped_to_the_selected_company(self):
        other_company = Empresa.objects.create(nombre="Empresa ajena Excel Test")
        own_machine = Maquina.objects.create(nombre="Equipo propio", empresa=self.empresa)
        own_point = PuntoMuestreo.objects.create(maquina=own_machine, nombre="Punto propio")
        foreign_machine = Maquina.objects.create(nombre="Equipo ajeno", empresa=other_company)
        foreign_point = PuntoMuestreo.objects.create(maquina=foreign_machine, nombre="Punto ajeno")
        self.token.cliente_empresa_id = str(self.empresa.pk)
        self.token.save(update_fields=["cliente_empresa_id"])

        workbook = generate_template_workbook(self.token)
        catalog_sheet = workbook["_CATALOGOS"]
        headers = {cell.value: cell.column for cell in catalog_sheet[1]}
        machines = [value for value in catalog_sheet.iter_cols(
            min_col=headers["Maquinas"], max_col=headers["Maquinas"], min_row=2, values_only=True
        ).__next__() if value]
        points = [value for value in catalog_sheet.iter_cols(
            min_col=headers["PuntosMuestreo"], max_col=headers["PuntosMuestreo"], min_row=2, values_only=True
        ).__next__() if value]

        self.assertEqual(machines, [f"{own_machine.pk} | {own_machine.nombre}"])
        self.assertEqual(points, [f"{own_point.pk} | {own_machine.nombre} | {own_point.nombre}"])
        self.assertNotIn(str(foreign_machine.pk), " ".join(machines))
        self.assertNotIn(str(foreign_point.pk), " ".join(points))

    def test_preview_rejects_assets_outside_template_company(self):
        other_company = Empresa.objects.create(nombre="Empresa ajena para previsualizacion")
        foreign_machine = Maquina.objects.create(nombre="Equipo ajeno", empresa=other_company)
        foreign_point = PuntoMuestreo.objects.create(maquina=foreign_machine, nombre="Punto ajeno")
        workbook = generate_template_workbook(self.token)
        ws = workbook["Aceites"]
        columns = template_columns("aceite")
        index = {key: position for position, (key, _) in enumerate(columns, start=1)}
        ws.cell(2, index["fecha_toma"], timezone.now())
        ws.cell(2, index["condicion"], "usada")
        ws.cell(2, index["referencia_marca"], "Referencia de prueba")
        ws.cell(2, index["punto_muestreo"], f"{foreign_point.pk} | {foreign_machine.nombre} | {foreign_point.nombre}")
        ws.cell(2, index[f"tecnico_{self.field.id}"], f"{self.item.id} | SAE 70W-90")

        _, errors = parse_row(
            ws,
            2,
            "aceite",
            technical_fields_by_type(),
            empresa_id=self.empresa.pk,
        )

        self.assertTrue(any("Punto de medida inválido" in error["message"] for error in errors))


class LoteMuestrasCreateSerializerTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Global Oil Lote Test")
        self.user = User.objects.create_user(
            email="lote-create@example.com",
            password="test-password",
            empresa=self.empresa,
        )

    def test_occasional_draft_keeps_manual_point_and_stays_draft(self):
        payload = {
            "tipo_cliente": "ocasional", "cliente_ocasional_nombre": "Taller ocasional",
            "contacto_nombre": "Contacto", "fecha_envio": "2026-10-18",
            "estado": "borrador", "usuario_registro": self.user.id,
            "muestras": [{"fecha_toma": "2026-10-18T10:00:00-05:00", "tipo_muestra": "aceite",
                          "condicion": "usada", "equipo_placa": "TAXI 0223", "punto_muestreo_manual": "Transmisión"}],
        }
        serializer = LoteMuestrasCreateSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        lote = serializer.save()
        muestra = lote.muestras.get()
        lote.refresh_from_db()
        self.assertEqual(lote.estado, "borrador")
        self.assertEqual(muestra.equipo_placa, "TAXI 0223")
        self.assertEqual(muestra.campos_adicionales["punto_muestreo_manual"], "Transmisión")
        row = LoteMuestraWorkspaceSerializer(muestra).data
        self.assertEqual(row["punto_muestreo"]["nombre"], "Transmisión")
        self.assertEqual(row["estado_flujo"]["code"], "borrador")
        lote.recalcular_estado()
        self.assertEqual(lote.estado, "borrador")

        from apps.muestras.api.serializers.ingresoLabLote.index import CreateIngresoLabLoteSerializer
        lab_serializer = CreateIngresoLabLoteSerializer(data={"lote": lote.id, "fecha_recepcion": timezone.now().isoformat()})
        self.assertFalse(lab_serializer.is_valid())
        self.assertIn("lote", lab_serializer.errors)

        self.user.is_superuser = True
        self.user.is_active = True
        self.user.save(update_fields=["is_superuser", "is_active"])
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(f"/api/lubrication/sample-batches/{lote.id}/register/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        lote.refresh_from_db()
        self.assertEqual(lote.estado, "registrado")

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
                    # The web form deliberately sends null for a manually
                    # identified sample; the serializer must accept it.
                    "punto_muestreo": None,
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

    def test_manual_sampling_point_creates_tree_point_for_manual_machine(self):
        payload = {
            "tipo_cliente": "registrado",
            "cliente_empresa": self.empresa.id,
            "contacto_nombre": "Contacto manual",
            "fecha_envio": "2026-10-18",
            "estado": "registrado",
            "usuario_registro": self.user.id,
            "muestras": [{
                "fecha_toma": "2026-10-18T10:00:00-05:00",
                "tipo_muestra": "aceite",
                "condicion": "usada",
                "equipo_placa": "TALLER-MANUAL-01",
                "punto_muestreo_manual": "Reductor lado motor",
                "referencia_marca": "Shell Omala S4 GX 220",
            }],
        }

        serializer = LoteMuestrasCreateSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        lote = serializer.save()
        muestra = lote.muestras.get()
        assignment = muestra.asignaciones_punto_muestreo.get(activa=True)

        self.assertEqual(muestra.referencia_equipo.codigo_equipo, "TALLER-MANUAL-01")
        self.assertEqual(assignment.punto_muestreo.nombre, "Reductor lado motor")
        self.assertEqual(assignment.punto_muestreo.maquina_id, muestra.referencia_equipo_id)
        root = Carpeta.objects.get(compania=self.empresa, typeFolder="root", id_parent_node="-1")
        machine_node = Carpeta.objects.get(machine=muestra.referencia_equipo)
        self.assertEqual(machine_node.id_parent_node, str(root.id))
        self.assertTrue(machine_node.isMachine)

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
