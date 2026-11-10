"""Executable contract tests for machine/point historical homologation."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from etl_global_oil_domain import build_point_rows, split_machine_and_point


class PointHomologationTest(unittest.TestCase):
    def test_draga_position_is_normalized_without_merging_distinct_points(self):
        source_names = (
            "DRAGA 3 - REDUCTOR MALACATE PROA DER",
            "DRAGA 3 - REDUCTOR MALACATE PROA IZQ",
            "MALACATE DE PROA LADO DERECHO DRAGA No.3",
            "MALACATE DE PROA LADO IZQUIERDO DRAGA No.3",
        )
        resolved = [split_machine_and_point(value) for value in source_names]
        self.assertEqual(resolved[0], ("DRAGA No.3", "REDUCTOR MALACATE PROA DER"))
        self.assertEqual(resolved[1], ("DRAGA No.3", "REDUCTOR MALACATE PROA IZQ"))
        self.assertEqual(resolved[2], ("DRAGA No.3", "MALACATE DE PROA LADO DERECHO"))
        self.assertEqual(resolved[3], ("DRAGA No.3", "MALACATE DE PROA LADO IZQUIERDO"))

    def test_same_machine_and_plate_merges_source_names_as_auditable_aliases(self):
        rows = [
            {"CLIENTE": "MINEROS ALUVIAL S.A.S.", "EQUIPO": "DRAGA 3 - REDUCTOR MALACATE PROA DER", "PLACA": "100015377", "LUBRICANTE": "GEAR 320", "Tipo": "Engranajes"},
            {"CLIENTE": "MINEROS ALUVIAL S.A.S.", "EQUIPO": "MALACATE DE PROA LADO DERECHO DRAGA No.3", "PLACA": 100015377.0, "LUBRICANTE": "GEAR 320", "Tipo": "Engranajes"},
        ]
        points = build_point_rows(rows)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["nombre_punto"], "REDUCTOR MALACATE PROA DER")
        self.assertEqual(points[0]["codigo_punto"], "100015377")
        self.assertEqual(
            points[0]["punto_origen"],
            "REDUCTOR MALACATE PROA DER | MALACATE DE PROA LADO DERECHO",
        )

    def test_machine_without_explicit_point_uses_its_own_name(self):
        self.assertEqual(
            split_machine_and_point("CHUMACERA DE TURBINA LADO NORTE UG3"),
            ("CHUMACERA DE TURBINA LADO NORTE UG3", "CHUMACERA DE TURBINA LADO NORTE UG3"),
        )

    def test_same_name_with_different_plates_gets_unambiguous_display_names(self):
        rows = [
            {"CLIENTE": "MINEROS ALUVIAL S.A.S.", "EQUIPO": "MOTOR", "PLACA": "100026495", "LUBRICANTE": "A", "Tipo": ""},
            {"CLIENTE": "MINEROS ALUVIAL S.A.S.", "EQUIPO": "MOTOR", "PLACA": "N-186", "LUBRICANTE": "A", "Tipo": ""},
        ]
        points = build_point_rows(rows)
        self.assertEqual({point["nombre_punto"] for point in points}, {"MOTOR · 100026495", "MOTOR · N-186"})


if __name__ == "__main__":
    unittest.main()
