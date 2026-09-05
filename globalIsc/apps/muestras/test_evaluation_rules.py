from django.test import SimpleTestCase

from apps.muestras.api.services.evaluation_rules import aggregate_evaluations


def evaluation(field, passed, estado=None):
    return {
        "field_id": field,
        "field": str(field),
        "passed": passed,
        "estado": estado or ("NORMAL" if passed else "CRITICO"),
    }


def result_evaluation(field, result_id, passed, estado=None):
    item = evaluation(field, passed, estado)
    item["result_id"] = result_id
    item["result_label"] = f"Resultado {result_id}"
    return item


class EvaluationRuleTests(SimpleTestCase):
    def test_any_red_field_makes_test_critical(self):
        outcome = aggregate_evaluations([
            evaluation(1, True),
            evaluation(2, False, "CRITICO"),
        ])
        self.assertFalse(outcome.passed)
        self.assertEqual(outcome.estado, "CRITICO")
        self.assertEqual(outcome.red_count, 1)

    def test_yellow_field_makes_test_undesired(self):
        outcome = aggregate_evaluations([
            evaluation(1, True),
            evaluation(2, False, "NO_DESEADO"),
        ])
        self.assertFalse(outcome.passed)
        self.assertEqual(outcome.estado, "NO_DESEADO")
        self.assertEqual(outcome.yellow_count, 1)

    def test_multiple_yellows_remain_undesired(self):
        outcome = aggregate_evaluations(
            [
                evaluation(1, False, "NO_DESEADO"),
                evaluation(2, False, "NO_DESEADO"),
            ],
            config={"modo": "semaforo", "amarillos_para_critico": 2},
        )
        self.assertEqual(outcome.estado, "NO_DESEADO")

    def test_informative_fields_do_not_drive_decision(self):
        outcome = aggregate_evaluations(
            [evaluation("comentario", False), evaluation("ferrosas", True)],
            config={"informativos": ["comentario"]},
        )
        self.assertTrue(outcome.passed)
        self.assertEqual(outcome.evaluated_count, 1)

    def test_missing_technical_information_has_priority(self):
        outcome = aggregate_evaluations([
            evaluation(1, True),
            evaluation(2, None, "SIN_INFORMACION_TECNICA"),
        ])
        self.assertIsNone(outcome.passed)
        self.assertEqual(outcome.estado, "SIN_INFORMACION_TECNICA")

    def test_legacy_thresholds_do_not_change_worst_state_rule(self):
        outcome = aggregate_evaluations(
            [
                result_evaluation(1, 10, False, "NO_DESEADO"),
                result_evaluation(2, 10, False, "NO_DESEADO"),
                result_evaluation(3, 20, False, "NO_DESEADO"),
            ],
            config={"resultados_amarillos_para_critico": 2},
            result_rules={"10": {"amarillos_para_critico": 2}},
        )

        self.assertEqual(outcome.estado, "NO_DESEADO")
        self.assertEqual(len(outcome.result_outcomes), 2)
        self.assertEqual(outcome.result_outcomes[0]["estado"], "NO_DESEADO")

    def test_two_yellow_results_keep_whole_test_undesired(self):
        outcome = aggregate_evaluations(
            [
                result_evaluation(1, 10, False, "NO_DESEADO"),
                result_evaluation(2, 20, False, "NO_DESEADO"),
            ],
            config={"resultados_amarillos_para_critico": 2},
        )

        self.assertEqual(outcome.estado, "NO_DESEADO")
        self.assertEqual(outcome.yellow_count, 2)
