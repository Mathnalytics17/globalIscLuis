"""Focused executable test for the file-only Global Oil ETL."""

import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).parent))
from etl_historica_global_oil import MASTER_COLUMNS, SAMPLE_COLUMNS, apply_client_scope, make_artifacts


class HistoricEtlTest(unittest.TestCase):
    def test_extracts_raw_data_and_preserves_qualified_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reportes.xlsx"
            knowledge = root / "conocimiento.xlsx"
            output = root / "output"
            headers = list(dict.fromkeys([*SAMPLE_COLUMNS, "APARIENCIA", "Ag", "Zn", "CONCLUSIÓN", "COM_1"]))
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Reporte OA"
            sheet.append([""] * len(headers))
            sheet.append(headers)
            values = {column: "" for column in headers}
            values.update({
                "OA": "OA-001", "FECHA": datetime(2026, 1, 2), "FECHA TOMA DE MUESTRA": datetime(2026, 1, 1),
                "CLIENTE": "Cliente A", "EQUIPO": "Equipo 1", "PLACA": "ABC123", "LUBRICANTE": "Aceite 46",
                "Tipo": "Hidraulico", "Viscosidad": "ISO 46", "Esp_Cal": "HM", "Responsable": "Analista",
                "APARIENCIA": "CLARA", "Ag": "<1", "Zn": 10, "CONCLUSIÓN": "Sin alarma", "COM_1": "Conservar",
            })
            sheet.append([values[column] for column in headers])
            workbook.create_sheet("Hoja2")
            workbook.save(reports)
            knowledge_book = Workbook()
            knowledge_book.active.title = "01_Limites_Metales"
            knowledge_book.active.append(["Metal", "Límite"])
            knowledge_book.active.append(["Ag", "1"])
            knowledge_book.save(knowledge)

            manifest = make_artifacts(reports, knowledge, output, replace=False, client_scope="all")

            self.assertEqual(manifest["controls"]["records"], 1)
            self.assertEqual(manifest["controls"]["unique_oa"], 1)
            self.assertFalse(manifest["database_written"])
            with (output / "staging" / "mediciones.csv").open(encoding="utf-8-sig", newline="") as artifact:
                measurements = list(csv.DictReader(artifact))
            silver = next(row for row in measurements if row["source_column"] == "Ag")
            self.assertEqual(silver["original_value"], "<1")
            self.assertEqual(silver["comparator"], "<")
            with (output / "reports" / "manifest.json").open(encoding="utf-8") as artifact:
                self.assertEqual(json.load(artifact)["controls"]["records"], 1)

    def test_accepts_later_dump_oa_sheet_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "registro_oa.xlsx"
            knowledge = root / "conocimiento.xlsx"
            output = root / "output"
            headers = list(dict.fromkeys([*SAMPLE_COLUMNS, "APARIENCIA", "Ag", "Zn", "CONCLUSIÓN"]))
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Dump OA"
            sheet.append([""] * len(headers))
            sheet.append(headers)
            values = {column: "" for column in headers}
            values.update({
                "OA": "OA-DUMP-001", "FECHA": datetime(2026, 1, 2), "FECHA TOMA DE MUESTRA": datetime(2026, 1, 1),
                "CLIENTE": "Cliente A", "EQUIPO": "Equipo 1", "PLACA": "ABC123", "LUBRICANTE": "Aceite 46",
                "Tipo": "Hidraulico", "Viscosidad": "ISO 46", "Esp_Cal": "HM", "Responsable": "Analista",
                "APARIENCIA": "CLARA", "Ag": "<1", "Zn": 10, "CONCLUSIÓN": "Sin alarma",
            })
            sheet.append([values[column] for column in headers])
            workbook.save(reports)
            knowledge_book = Workbook()
            knowledge_book.active.title = "01_Limites_Metales"
            knowledge_book.active.append(["Metal", "Límite"])
            knowledge_book.save(knowledge)

            manifest = make_artifacts(reports, knowledge, output, replace=False, client_scope="all")

            self.assertEqual(manifest["controls"]["records"], 1)

    def test_mineros_scope_keeps_sas_and_sas_bic_legal_spellings(self):
        rows = [
            {"CLIENTE": "MINEROS ALUVIAL S.A.S.", "OA": "old"},
            {"CLIENTE": "MINEROS ALUVIAL SAS BIC", "OA": "new"},
        ]
        selected = apply_client_scope(rows, "mineros")
        self.assertEqual([row["OA"] for row in selected], ["old", "new"])


if __name__ == "__main__":
    unittest.main()
