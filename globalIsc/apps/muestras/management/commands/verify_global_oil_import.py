"""Read-only integrity report for the reproducible Global Oil historical import."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.resultado.api.models.index import Resultado


class Command(BaseCommand):
    help = "Verifica OA, asignaciones y resultados de la migración histórica Global Oil sin escribir datos."

    def add_arguments(self, parser):
        parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))

    def handle(self, *args, **options):
        artifacts = options["artifacts"]
        required = [
            artifacts / "staging" / "reportes_oa_raw.jsonl",
            artifacts / "staging" / "api_result_payloads.jsonl",
            artifacts / "staging" / "api_result_payloads_physical.jsonl",
            artifacts / "staging" / "oa_pruebas_muestra.json",
            artifacts / "reports" / "carga_api_muestras.json",
        ]
        missing_files = [str(path) for path in required if not path.is_file()]
        if missing_files:
            raise CommandError(f"Faltan artefactos ETL: {missing_files}")

        def jsonl(path):
            return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]

        source = jsonl(required[0])
        compound = jsonl(required[1])
        physical = jsonl(required[2])
        mapping = json.loads(required[3].read_text(encoding="utf-8"))
        import_audit = json.loads(required[4].read_text(encoding="utf-8"))
        oa_source = {str(item.get("oa") or "").strip() for item in import_audit}
        expected = [item for item in compound + physical if str(item.get("oa") or "").strip() in oa_source]
        imported = Muestra.objects.filter(campos_adicionales__has_key="oa_origen")
        oa_imported = set(imported.values_list("campos_adicionales__oa_origen", flat=True))
        missing_oa = sorted(oa_source - oa_imported)
        duplicate_oa = sorted(
            oa for oa in oa_imported
            if imported.filter(campos_adicionales__oa_origen=oa).count() > 1
        )
        expected_assignments = []
        missing_mapping = []
        for item in expected:
            test_id = mapping.get(str(item["oa"]), {}).get(item["test_code"])
            if test_id is None:
                missing_mapping.append({"oa": item["oa"], "test": item["test_code"]})
            else:
                expected_assignments.append(test_id)
        completed_assignments = set(
            Resultado.objects.filter(prueba_muestra_id__in=expected_assignments)
            .exclude(estatus="rechazado")
            .values_list("prueba_muestra_id", flat=True)
        )
        missing_results = [
            {"oa": item["oa"], "test": item["test_code"], "prueba_muestra": mapping.get(str(item["oa"]), {}).get(item["test_code"])}
            for item in expected
            if mapping.get(str(item["oa"]), {}).get(item["test_code"]) not in completed_assignments
        ]
        report = {
            "source_oa": len(oa_source), "imported_oa": len(oa_imported),
            "expected_compound_results": len(compound), "expected_physical_results": len(physical),
            "expected_results": len(expected), "resultados_registrados": Resultado.objects.count(),
            "pruebas_muestra_registradas": PruebaMuestra.objects.count(),
            "missing_oa": missing_oa, "duplicate_oa": duplicate_oa,
            "missing_mapping": missing_mapping, "missing_results": missing_results,
            "valid": not any([missing_oa, duplicate_oa, missing_mapping, missing_results]),
        }
        output = artifacts / "reports" / "verificacion_integridad_importacion.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(json.dumps({"valid": report["valid"], "expected": len(expected), "missing_results": len(missing_results), "report": str(output)}, ensure_ascii=False))
