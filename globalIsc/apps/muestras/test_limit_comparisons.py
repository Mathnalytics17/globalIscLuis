from types import SimpleNamespace

from django.test import TestCase

from apps.misc.api.models.dynamicTechnicalConfig.index import EscalaComparacion, EscalaComparacionItem
from apps.muestras.api.services.limit_engine import _evaluate_typed


def field(comparison, operator, **extra):
    return SimpleNamespace(tipo_comparacion=comparison, operador=operator, **extra)


class TypedLimitComparisonTests(TestCase):
    def test_numeric_comparisons(self):
        self.assertTrue(_evaluate_typed("9.5", field("numerica", "max"), "10"))
        self.assertFalse(_evaluate_typed("10.1", field("numerica", "max"), "10"))
        self.assertTrue(_evaluate_typed("10", field("numerica", "min"), "10"))
        self.assertTrue(_evaluate_typed("10", field("numerica", "eq"), "10"))
        self.assertTrue(_evaluate_typed("11", field("numerica", "neq"), "10"))

    def test_boolean_expected_value_can_be_inverted_per_test(self):
        expected_no = field("booleano", "eq")
        self.assertTrue(_evaluate_typed("No", expected_no, "No"))
        self.assertFalse(_evaluate_typed("Si", expected_no, "No"))

        expected_yes = field("booleano", "eq")
        self.assertTrue(_evaluate_typed("Si", expected_yes, "Si"))
        self.assertFalse(_evaluate_typed("No", expected_yes, "Si"))

    def test_ordinal_scale_uses_configured_order(self):
        scale = EscalaComparacion.objects.create(nombre="Olor", codigo="olor_test")
        for order, label in enumerate(["Excelente", "Bueno", "Regular", "Malo"], start=1):
            EscalaComparacionItem.objects.create(
                escala=scale,
                etiqueta=label,
                valor_normalizado=label,
                orden=order,
            )
        ordinal = field(
            "escala_ordinal",
            "scale_max",
            escala_comparacion_id=scale.id,
            modo_ordinal="orden",
        )
        self.assertTrue(_evaluate_typed("Excelente", ordinal, "Bueno"))
        self.assertTrue(_evaluate_typed("Bueno", ordinal, "Bueno"))
        self.assertFalse(_evaluate_typed("Regular", ordinal, "Bueno"))

    def test_closed_list_comparison(self):
        option = field("opcion", "in")
        self.assertTrue(_evaluate_typed("Aceptable", option, "Bueno,Aceptable"))
        self.assertFalse(_evaluate_typed("Malo", option, "Bueno,Aceptable"))
