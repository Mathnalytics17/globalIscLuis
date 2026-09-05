from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.muestras.api.services.evaluation_rules import aggregate_evaluations
from apps.muestras.api.services.limit_engine import _evaluate_semaphore_rule


class SemaphoreEvaluationTests(SimpleTestCase):
    def setUp(self):
        self.field = SimpleNamespace(
            tipo_comparacion="numerica",
            operador="between",
        )

    def test_numeric_rule_returns_green_yellow_and_red(self):
        rule = {
            "usar_amarillo": True,
            "min_critico": 5,
            "min_aceptable": 10,
            "max_aceptable": 20,
            "max_critico": 25,
        }

        self.assertEqual(_evaluate_semaphore_rule(15, self.field, rule)["estado"], "NORMAL")
        self.assertEqual(_evaluate_semaphore_rule(22, self.field, rule)["estado"], "NO_DESEADO")
        self.assertEqual(_evaluate_semaphore_rule(30, self.field, rule)["estado"], "CRITICO")

    def test_without_yellow_outside_acceptable_is_critical(self):
        rule = {
            "usar_amarillo": False,
            "min_aceptable": 10,
            "max_aceptable": 20,
        }
        self.assertEqual(_evaluate_semaphore_rule(21, self.field, rule)["estado"], "CRITICO")

    def test_minimum_rule_uses_only_lower_boundaries(self):
        self.field.operador = "min"
        rule = {
            "usar_amarillo": True,
            "min_critico": 5,
            "min_aceptable": 10,
        }

        self.assertEqual(_evaluate_semaphore_rule(12, self.field, rule)["estado"], "NORMAL")
        self.assertEqual(_evaluate_semaphore_rule(7, self.field, rule)["estado"], "NO_DESEADO")
        self.assertEqual(_evaluate_semaphore_rule(3, self.field, rule)["estado"], "CRITICO")

    def test_maximum_rule_uses_only_upper_boundaries(self):
        self.field.operador = "max"
        rule = {
            "usar_amarillo": True,
            "max_aceptable": 10,
            "max_critico": 15,
        }

        self.assertEqual(_evaluate_semaphore_rule(8, self.field, rule)["estado"], "NORMAL")
        self.assertEqual(_evaluate_semaphore_rule(12, self.field, rule)["estado"], "NO_DESEADO")
        self.assertEqual(_evaluate_semaphore_rule(18, self.field, rule)["estado"], "CRITICO")

    def test_multiple_yellows_remain_undesired(self):
        evaluations = [
            {"field": "a", "estado": "NO_DESEADO", "passed": False},
            {"field": "b", "estado": "NO_DESEADO", "passed": False},
            {"field": "c", "estado": "NORMAL", "passed": True},
        ]
        outcome = aggregate_evaluations(
            evaluations,
            config={"modo": "semaforo", "amarillos_para_critico": 2},
        )
        self.assertEqual(outcome.estado, "NO_DESEADO")
        self.assertEqual(outcome.yellow_count, 2)

    def test_single_yellow_remains_undesired(self):
        outcome = aggregate_evaluations(
            [{"field": "a", "estado": "NO_DESEADO", "passed": False}],
            config={"modo": "semaforo", "amarillos_para_critico": 2},
        )
        self.assertEqual(outcome.estado, "NO_DESEADO")

    def test_legacy_yellow_threshold_is_ignored(self):
        outcome = aggregate_evaluations(
            [
                {"field": "a", "estado": "NO_DESEADO", "passed": False},
                {"field": "b", "estado": "NO_DESEADO", "passed": False},
            ],
            config={"resultados_amarillos_para_critico": 1},
            result_rules={"Resultado principal": {"amarillos_para_critico": 1}},
        )
        self.assertEqual(outcome.estado, "NO_DESEADO")
