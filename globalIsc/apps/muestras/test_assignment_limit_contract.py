import json
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.muestras.api.serializers.pruebasMuestra.index import (
    FlexibleCriterionValueField,
    _inherit_criterion_limit_value,
)
from apps.muestras.api.services.limit_engine import (
    _assigned_limit_value_for_field,
    _evaluate_semaphore_rule,
)


class AssignmentLimitContractTests(SimpleTestCase):
    def setUp(self):
        self.field = SimpleNamespace(
            id=7,
            codigo="resultado_principal_valor",
            operador="min",
            tipo_comparacion="numerica",
        )
        self.configured_rule = {
            "resultado_principal_valor": {
                "usar_amarillo": True,
                "min_critico": 5,
                "min_aceptable": 10,
            }
        }
        self.contextual_rule = {
            "resultado_principal_valor": {
                "usar_amarillo": True,
                "min_critico": 100,
                "min_aceptable": 200,
            }
        }
        self.criterion = SimpleNamespace(
            valores_limite=self.configured_rule,
            valor="10",
        )

    def test_contextual_assignment_rule_is_not_replaced_by_configured_default(self):
        attrs = {
            "criterio_limite_valor": FlexibleCriterionValueField().to_internal_value(
                self.contextual_rule
            )
        }

        _inherit_criterion_limit_value(attrs, self.criterion)

        self.assertEqual(json.loads(attrs["criterio_limite_valor"]), self.contextual_rule)

    def test_configured_field_map_is_inherited_when_assignment_has_no_override(self):
        attrs = {}

        _inherit_criterion_limit_value(attrs, self.criterion)

        self.assertEqual(json.loads(attrs["criterio_limite_valor"]), self.configured_rule)

    def test_contextual_rule_survives_serialization_and_drives_all_three_states(self):
        stored_value = FlexibleCriterionValueField().to_internal_value(self.contextual_rule)
        rule = _assigned_limit_value_for_field(stored_value, self.field)

        self.assertEqual(rule, self.contextual_rule["resultado_principal_valor"])
        self.assertEqual(_evaluate_semaphore_rule(250, self.field, rule)["estado"], "NORMAL")
        self.assertEqual(_evaluate_semaphore_rule(150, self.field, rule)["estado"], "NO_DESEADO")
        self.assertEqual(_evaluate_semaphore_rule(50, self.field, rule)["estado"], "CRITICO")

    def test_without_yellow_context_goes_directly_from_green_to_red(self):
        contextual = {
            "resultado_principal_valor": {
                "usar_amarillo": False,
                "min_aceptable": 200,
            }
        }
        stored_value = FlexibleCriterionValueField().to_internal_value(contextual)
        rule = _assigned_limit_value_for_field(stored_value, self.field)

        self.assertEqual(_evaluate_semaphore_rule(250, self.field, rule)["estado"], "NORMAL")
        self.assertEqual(_evaluate_semaphore_rule(150, self.field, rule)["estado"], "CRITICO")
