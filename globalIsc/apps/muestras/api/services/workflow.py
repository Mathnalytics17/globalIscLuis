from dataclasses import dataclass

from django.db.models import Count, Q
from rest_framework.exceptions import ValidationError

from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra


LOCKED_STATES = {"cancelado", "reportado"}


@dataclass(frozen=True)
class BatchCapabilities:
    enter_lab: bool
    assign_tests: bool
    enter_results: bool
    review_results: bool
    interpret_results: bool

    def to_dict(self):
        return {
            "ingresar_laboratorio": self.enter_lab,
            "asignar_pruebas": self.assign_tests,
            "ingresar_resultados": self.enter_results,
            "revisar_resultados": self.review_results,
            "interpretar_resultados": self.interpret_results,
        }


def capabilities_for_batch(batch):
    total_samples = _count(batch, "total_muestras_db", lambda: batch.muestras.count())
    entered_samples = _count(
        batch,
        "muestras_ingresadas_db",
        lambda: batch.muestras.filter(is_ingresado=True).count(),
    )
    assignment_counts = None

    def assignment_count(name):
        nonlocal assignment_counts
        if assignment_counts is None:
            assignment_counts = PruebaMuestra.objects.filter(
                muestra__lote=batch,
                estado_asignacion="confirmada",
            ).aggregate(
                assigned=Count("id"),
                completed=Count("id", filter=Q(completada=True)),
                reviewed=Count("id", filter=Q(is_revisada=True)),
            )
        return assignment_counts[name]

    assigned = _count(batch, "pruebas_asignadas_db", lambda: assignment_count("assigned"))
    completed = _count(batch, "pruebas_completadas_db", lambda: assignment_count("completed"))
    reviewed = _count(batch, "pruebas_revisadas_db", lambda: assignment_count("reviewed"))

    unlocked = batch.estado not in LOCKED_STATES
    all_entered = total_samples > 0 and entered_samples == total_samples
    has_review = reviewed > 0
    return BatchCapabilities(
        enter_lab=unlocked and total_samples > 0 and entered_samples == 0,
        assign_tests=unlocked and all_entered and not has_review,
        enter_results=unlocked and all_entered and assigned > 0 and not has_review,
        review_results=unlocked and assigned > 0 and completed == assigned and reviewed < assigned,
        interpret_results=unlocked and assigned > 0 and reviewed == assigned,
    )


def require_batch_operation(batch, operation):
    capabilities = capabilities_for_batch(batch).to_dict()
    if not capabilities.get(operation, False):
        raise ValidationError({
            "detail": f"La operacion '{operation}' no esta disponible para el estado actual del lote.",
            "estado": batch.estado,
            "acciones_disponibles": capabilities,
        })


def _count(instance, annotation, fallback):
    value = getattr(instance, annotation, None)
    return int(value) if value is not None else int(fallback())
