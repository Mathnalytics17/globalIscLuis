import json
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CriterioEvaluacionLimite,
    EscalaComparacion,
    EscalaComparacionItem,
    CatalogoTecnico,
    CatalogoTecnicoItem,
    PruebaFuenteLimite,
    PruebaLimiteCampo,
)
from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.models.lotesPruebasPredefinidos.index import (
    LotePruebasPredefinido,
    LotePruebasPredefinidoDetalle,
)
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.services.limit_contract_reconciliation import (
    reconcile_definition_contracts,
    reconcile_test_assignments,
    canonicalize_field_rule,
    reconcile_test_predefined_details,
)
from apps.muestras.api.serializers.pruebasMuestra.index import (
    BatchAssignPruebaItemSerializer,
    BatchAssignPruebasSerializer,
)
from apps.users.api.models.index import User


class LimitContractReconciliationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="limit-reconcile@example.com",
            password="test-password",
            is_active=True,
            role=User.Role.GLOBAL,
        )
        self.batch = LoteMuestras.objects.create(
            id="LRECON001",
            fecha_envio=date.today(),
            usuario_registro=self.user,
        )
        self.sample = Muestra.objects.create(
            id="MRECON001",
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )
        self.test = Prueba.objects.create(nombre_variable="Reconcile", acronimo="RECON")
        self.rule = {
            "min_critico": "22",
            "min_aceptable": "23",
            "usar_amarillo": True,
        }
        self.source = PruebaFuenteLimite.objects.create(
            prueba=self.test,
            tipo_limite="global",
            configuracion_regla={
                "modo": "semaforo",
                "campos": [{
                    "codigo": "resultado",
                    "operador": "min",
                    "tipo_comparacion": "numerica",
                    "origen_limite": "directo",
                    "valor_global": self.rule,
                }],
            },
        )
        self.field = PruebaLimiteCampo.objects.create(
            fuente_limite=self.source,
            nombre="Resultado",
            codigo="resultado",
            operador="min",
            tipo_comparacion="numerica",
            valor_global=json.dumps(self.rule),
        )

    def test_old_scalar_assignment_is_replaced_with_current_direct_rule(self):
        assignment = PruebaMuestra.objects.create(
            muestra=self.sample,
            prueba=self.test,
            usuario_solicitud=self.user,
            criterio_limite_valor=json.dumps({str(self.field.id): "123"}),
        )

        changes = reconcile_test_assignments(self.test, reset_direct_defaults=True)

        assignment.refresh_from_db()
        stored = json.loads(assignment.criterio_limite_valor)
        self.assertEqual(stored[str(self.field.id)], self.rule)
        self.assertEqual(len(changes), 1)

    def test_scalar_catalog_values_are_converted_to_canonical_rules(self):
        self.source.tipo_limite = "catalogo"
        self.source.configuracion_regla["campos"][0]["origen_limite"] = "catalogo"
        self.source.save(update_fields=["tipo_limite", "configuracion_regla", "updated_at"])
        self.field.valor_global = None
        self.field.save(update_fields=["valor_global", "updated_at"])
        criterion = CriterioEvaluacionLimite.objects.create(
            fuente_limite=self.source,
            nombre="Item",
            codigo="item",
            valores_limite={"resultado": "12"},
        )

        reconcile_definition_contracts()

        criterion.refresh_from_db()
        self.assertEqual(criterion.valores_limite["resultado"], {
            "min_critico": "",
            "min_aceptable": "12",
            "usar_amarillo": False,
        })

    def test_legacy_field_code_separators_are_migrated_without_losing_value(self):
        self.source.tipo_limite = "catalogo"
        self.source.configuracion_regla["campos"][0]["codigo"] = "iso_4614"
        self.source.configuracion_regla["campos"][0]["origen_limite"] = "catalogo"
        self.source.save(update_fields=["tipo_limite", "configuracion_regla", "updated_at"])
        self.field.codigo = "iso_4614"
        self.field.valor_global = None
        self.field.save(update_fields=["codigo", "valor_global", "updated_at"])
        criterion = CriterioEvaluacionLimite.objects.create(
            fuente_limite=self.source,
            nombre="ISO",
            codigo="iso",
            valores_limite={"iso_4_6_14": "12"},
        )

        reconcile_definition_contracts()

        criterion.refresh_from_db()
        self.assertEqual(criterion.valores_limite["iso_4614"]["min_aceptable"], "12")

    def test_dry_run_reports_without_mutating(self):
        assignment = PruebaMuestra.objects.create(
            muestra=self.sample,
            prueba=self.test,
            usuario_solicitud=self.user,
            criterio_limite_valor=json.dumps({str(self.field.id): "123"}),
        )

        changes = reconcile_test_assignments(
            self.test,
            reset_direct_defaults=True,
            dry_run=True,
        )

        assignment.refresh_from_db()
        self.assertEqual(json.loads(assignment.criterio_limite_valor)[str(self.field.id)], "123")
        self.assertEqual(len(changes), 1)

    def test_scale_boundaries_use_the_same_normalized_value_as_select_options(self):
        scale = EscalaComparacion.objects.create(nombre="Color", codigo="color_reconcile")
        EscalaComparacionItem.objects.create(
            escala=scale,
            etiqueta="L3",
            valor_normalizado="l3",
            orden=1,
        )
        EscalaComparacionItem.objects.create(
            escala=scale,
            etiqueta="3",
            valor_normalizado="3",
            orden=2,
        )
        self.field.tipo_comparacion = "escala"
        self.field.escala_comparacion = scale

        rule = canonicalize_field_rule(self.field, {
            "min_critico": "L3",
            "min_aceptable": "3",
            "usar_amarillo": True,
        })

        self.assertEqual(rule["min_critico"], "l3")
        self.assertEqual(rule["min_aceptable"], "3")

    def test_predefined_batch_drops_old_catalog_and_uses_current_direct_rule(self):
        catalog = CatalogoTecnico.objects.create(
            nombre="Catálogo anterior",
            codigo="catalogo_anterior",
            tipo_muestra="aceite",
        )
        item = CatalogoTecnicoItem.objects.create(catalogo=catalog, nombre="Ítem anterior")
        predefined = LotePruebasPredefinido.objects.create(nombre="Plantilla antigua")
        detail = LotePruebasPredefinidoDetalle.objects.create(
            lote=predefined,
            prueba=self.test,
            criterio_limite_catalogo=catalog,
            criterio_limite_item=item,
            criterio_limite_valor=json.dumps({str(self.field.id): "123"}),
        )

        changes = reconcile_test_predefined_details(
            self.test,
            reset_direct_defaults=True,
        )

        detail.refresh_from_db()
        self.assertIsNone(detail.criterio_limite_catalogo_id)
        self.assertIsNone(detail.criterio_limite_item_id)
        self.assertEqual(json.loads(detail.criterio_limite_valor)[str(self.field.id)], self.rule)
        self.assertEqual(len(changes), 1)

    def test_open_assignment_with_obsolete_catalog_is_safely_sanitized(self):
        catalog = CatalogoTecnico.objects.create(
            nombre="Catálogo anterior",
            codigo="catalogo_payload_anterior",
            tipo_muestra="aceite",
        )
        item = CatalogoTecnicoItem.objects.create(catalogo=catalog, nombre="Ítem anterior")

        serializer = BatchAssignPruebaItemSerializer(data={
            "prueba": self.test.id,
            "criterio_limite_catalogo": catalog.id,
            "criterio_limite_item": item.id,
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["criterio_limite_catalogo"])
        self.assertIsNone(serializer.validated_data["criterio_limite_item"])

    def test_identical_duplicate_tests_from_legacy_template_are_deduplicated(self):
        row = {"prueba": self.test.id, "criterio_limite_valor": {str(self.field.id): self.rule}}
        serializer = BatchAssignPruebasSerializer(data={
            "lote_id": self.batch.id,
            "sample_ids": [self.sample.id],
            "pruebas": [row, row],
            "estado_asignacion": "confirmada",
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(serializer.validated_data["pruebas"]), 1)

    def test_conflicting_duplicate_tests_are_rejected(self):
        serializer = BatchAssignPruebasSerializer(data={
            "lote_id": self.batch.id,
            "sample_ids": [self.sample.id],
            "pruebas": [
                {"prueba": self.test.id, "criterio_limite_valor": {str(self.field.id): self.rule}},
                {"prueba": self.test.id, "criterio_limite_valor": {str(self.field.id): {
                    **self.rule,
                    "min_aceptable": "99",
                }}},
            ],
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("configuraciones diferentes", str(serializer.errors))
