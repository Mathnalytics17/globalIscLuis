import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CriterioEvaluacionLimite,
    PruebaFuenteLimite,
    PruebaLimiteCampo,
)
from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.models.lotesPruebasPredefinidos.index import LotePruebasPredefinidoDetalle
from apps.misc.api.services.limit_contract import reconcile_limit_contract
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.services.limit_contract_reconciliation import (
    reconcile_all_assignments,
    reconcile_all_predefined_details,
    reconcile_definition_contracts,
    reconcile_test_assignments,
    reconcile_test_predefined_details,
)


class Command(BaseCommand):
    help = "Reconecta y normaliza los límites con el contrato de semáforo actual."

    def add_arguments(self, parser):
        parser.add_argument("--test-id", type=int, dest="test_id")
        parser.add_argument("--apply", action="store_true", help="Aplica los cambios. Sin esta opción solo informa.")
        parser.add_argument(
            "--reset-direct-defaults",
            action="store_true",
            help="Actualiza asignaciones directas con el valor vigente configurado en Límites.",
        )

    def _snapshot(self):
        return {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sources": list(PruebaFuenteLimite.objects.values()),
            "fields": list(PruebaLimiteCampo.objects.values()),
            "criteria": list(CriterioEvaluacionLimite.objects.values()),
            "assignments": list(PruebaMuestra.objects.values(
                "id", "muestra_id", "prueba_id", "criterio_evaluacion_id",
                "criterio_limite_catalogo_id", "criterio_limite_item_id",
                "criterio_limite_escala_id", "criterio_limite_escala_item_id",
                "criterio_limite_valor", "evaluacion_limite", "estado_limite",
            )),
            "predefined_batch_details": list(LotePruebasPredefinidoDetalle.objects.values()),
        }

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        tests = Prueba.objects.all().order_by("id")
        if options.get("test_id"):
            tests = tests.filter(pk=options["test_id"])

        structural_changes = 0
        if apply_changes:
            backup_dir = Path(settings.BASE_DIR) / "tmp" / "limit_contract_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = backup_dir / f"limit-contracts-{stamp}.json"
            backup_path.write_text(
                json.dumps(self._snapshot(), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            self.stdout.write(f"Respaldo: {backup_path}")
            for test in tests:
                structural_changes += reconcile_limit_contract(test)

        definition_changes = reconcile_definition_contracts(dry_run=not apply_changes)
        if options.get("test_id"):
            test = tests.first()
            assignment_changes = reconcile_test_assignments(
                test,
                reset_direct_defaults=options["reset_direct_defaults"],
                dry_run=not apply_changes,
            ) if test else []
            predefined_changes = reconcile_test_predefined_details(
                test,
                reset_direct_defaults=options["reset_direct_defaults"],
                dry_run=not apply_changes,
            ) if test else []
        else:
            assignment_changes = reconcile_all_assignments(
                reset_direct_defaults=options["reset_direct_defaults"],
                dry_run=not apply_changes,
            )
            predefined_changes = reconcile_all_predefined_details(
                reset_direct_defaults=options["reset_direct_defaults"],
                dry_run=not apply_changes,
            )

        self.stdout.write(self.style.SUCCESS(
            f"{'APLICADOS' if apply_changes else 'PREVISUALIZADOS'}: "
            f"{structural_changes} contratos estructurales, "
            f"{len(definition_changes)} definiciones, {len(assignment_changes)} asignaciones "
            f"y {len(predefined_changes)} detalles predefinidos; "
            f"pruebas revisadas: {tests.count()}."
        ))
        for change in assignment_changes:
            self.stdout.write(
                f"- asignación {change['assignment']} · {change['test']} · muestra {change['sample']}"
            )
        for change in predefined_changes:
            self.stdout.write(
                f"- predefinido {change['detail']} · {change['test']} · lote {change['batch']}"
            )
