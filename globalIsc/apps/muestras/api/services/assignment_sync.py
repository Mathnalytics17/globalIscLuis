from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.resultado.api.models.index import Resultado
from apps.misc.api.models.dynamicTechnicalConfig.index import PruebaFuenteLimite


ASSIGNMENT_UPDATE_FIELDS = [
    "usuario_solicitud",
    "equipo_configurado",
    "metodo_configurado",
    "condicion_catalogo",
    "condicion_configurada",
    "unidad_configurada",
    "configuracion_resultados",
    "unidad",
    "estado_asignacion",
    "fecha_confirmacion",
    "lote_predefinido",
    "criterio_evaluacion",
    "criterio_limite_catalogo",
    "criterio_limite_item",
    "criterio_limite_escala",
    "criterio_limite_escala_item",
    "criterio_limite_valor",
]

CRITERION_UPDATE_FIELDS = [
    "criterio_evaluacion",
    "criterio_limite_catalogo",
    "criterio_limite_item",
    "criterio_limite_escala",
    "criterio_limite_escala_item",
    "criterio_limite_valor",
]


@dataclass
class AssignmentSyncResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    protected: list[int] = field(default_factory=list)
    instances: list[PruebaMuestra] = field(default_factory=list)


def _suggest_criterion(item, sample):
    if item.get("criterio_evaluacion"):
        return item.get("criterio_evaluacion")
    source = PruebaFuenteLimite.objects.filter(
        prueba=item["prueba"], activo=True, deleted_at__isnull=True,
        modo_seleccion="desde_muestra_editable",
    ).first()
    if not source:
        return None
    selected_items = set(
        sample.atributos_tecnicos.filter(desconocido=False, item__isnull=False)
        .values_list("item_id", flat=True)
    )
    for candidate in source.criterios.filter(activo=True, deleted_at__isnull=True).prefetch_related("selecciones_catalogo"):
        required = set(candidate.selecciones_catalogo.values_list("item_id", flat=True))
        if required and required.issubset(selected_items):
            return candidate
    return None



def _suggest_sample_catalog_attribute(item, sample):
    """Infer technical criterion from the sample when the test limit source uses a sample technical catalog."""
    if item.get("criterio_limite_item"):
        return None

    source_qs = PruebaFuenteLimite.objects.filter(
        prueba=item["prueba"],
        activo=True,
        deleted_at__isnull=True,
    ).exclude(tipo_limite__in=["global", "sin_limite"]).select_related(
        "catalogo_fuente",
        "campo_tecnico_muestra",
        "campo_tecnico_muestra__catalogo",
    )

    selected_catalog = item.get("criterio_limite_catalogo")
    if selected_catalog:
        source_qs = source_qs.filter(catalogo_fuente=selected_catalog)

    for source in source_qs:
        relations = list(source.catalogos_configurados.filter(activo=True).select_related(
            "catalogo", "campo_tecnico_muestra", "campo_tecnico_muestra__catalogo"
        ))
        if not relations:
            relations = [source]

        for relation in relations:
            catalog = getattr(relation, "catalogo", None) or source.catalogo_fuente or getattr(source.campo_tecnico_muestra, "catalogo", None)
            field = getattr(relation, "campo_tecnico_muestra", None) or source.campo_tecnico_muestra
            if not catalog:
                continue

            attrs = sample.atributos_tecnicos.filter(
                catalogo=catalog,
                desconocido=False,
                item__isnull=False,
            ).select_related("catalogo", "item", "campo_tecnico")

            if getattr(field, "pk", None):
                attrs = attrs.filter(campo_tecnico_id=field.pk)

            attribute = attrs.first()
            if attribute:
                return attribute
    return None


def _assignment_values(item, *, sample, user, estado_asignacion, lote_predefinido, current=None):
    confirmed_at = None
    if estado_asignacion == "confirmada":
        confirmed_at = getattr(current, "fecha_confirmacion", None) or timezone.now()

    condition = item.get("condicion")
    inferred_attribute = _suggest_sample_catalog_attribute(item, sample)
    inferred_catalog = inferred_attribute.catalogo if inferred_attribute else None
    inferred_item = inferred_attribute.item if inferred_attribute else None
    explicit_catalog = item.get("criterio_limite_catalogo")
    explicit_item = item.get("criterio_limite_item")
    return {
        "usuario_solicitud_id": user.pk,
        "equipo_configurado_id": getattr(item.get("equipo_prueba"), "pk", None),
        "metodo_configurado_id": getattr(item.get("metodo_equipo"), "pk", None),
        "condicion_catalogo_id": getattr(condition, "pk", None),
        "condicion_configurada": item.get("condicion_texto"),
        "unidad_configurada": item.get("unidad"),
        "configuracion_resultados": item.get("configuracion_resultados") or {},
        "unidad": item.get("unidad"),
        "estado_asignacion": estado_asignacion,
        "fecha_confirmacion": confirmed_at,
        "lote_predefinido_id": getattr(lote_predefinido, "pk", None),
        "criterio_evaluacion_id": getattr(_suggest_criterion(item, sample), "pk", None),
        "criterio_limite_catalogo_id": getattr(explicit_catalog or inferred_catalog, "pk", None),
        "criterio_limite_item_id": getattr(explicit_item or inferred_item, "pk", None),
        "criterio_limite_escala_id": getattr(item.get("criterio_limite_escala"), "pk", None),
        "criterio_limite_escala_item_id": getattr(item.get("criterio_limite_escala_item"), "pk", None),
        "criterio_limite_valor": item.get("criterio_limite_valor"),
    }


def _apply_values(instance, values, fields):
    changed = False
    for field_name in fields:
        attribute = f"{field_name}_id" if f"{field_name}_id" in values else field_name
        next_value = values[attribute]
        if getattr(instance, attribute) != next_value:
            setattr(instance, attribute, next_value)
            changed = True
    return changed


@transaction.atomic
def synchronize_batch_assignments(*, lote, muestras, pruebas, estado_asignacion, lote_predefinido, user):
    """Make assignments for the selected samples match the submitted desired state."""
    result = AssignmentSyncResult()
    sample_ids = [sample.pk for sample in muestras]
    desired_test_ids = {item["prueba"].pk for item in pruebas}

    existing = list(
        PruebaMuestra.objects.select_for_update()
        .filter(muestra_id__in=sample_ids)
        .select_related("muestra", "prueba")
    )
    existing_by_key = {(item.muestra_id, item.prueba_id): item for item in existing}
    result_ids = set(
        Resultado.objects.filter(prueba_muestra_id__in=[item.pk for item in existing])
        .values_list("prueba_muestra_id", flat=True)
    )
    protected_ids = {
        item.pk
        for item in existing
        if item.completada or item.is_revisada or item.pk in result_ids
    }

    obsolete = [
        item for item in existing
        if item.prueba_id not in desired_test_ids
    ]
    removable_ids = [item.pk for item in obsolete if item.pk not in protected_ids]
    result.protected.extend(item.pk for item in obsolete if item.pk in protected_ids)
    if removable_ids:
        deleted, _ = PruebaMuestra.objects.filter(pk__in=removable_ids).delete()
        result.deleted = len(removable_ids)

    to_create = []
    to_update = []
    protected_to_recalculate = []

    for sample in muestras:
        for item in pruebas:
            key = (sample.pk, item["prueba"].pk)
            instance = existing_by_key.get(key)
            values = _assignment_values(
                item,
                sample=sample,
                user=user,
                estado_asignacion=estado_asignacion,
                lote_predefinido=lote_predefinido,
                current=instance,
            )
            if instance is None:
                to_create.append(
                    PruebaMuestra(
                        muestra_id=sample.pk,
                        prueba_id=item["prueba"].pk,
                        **values,
                    )
                )
                continue

            editable_fields = CRITERION_UPDATE_FIELDS if instance.pk in protected_ids else ASSIGNMENT_UPDATE_FIELDS
            if _apply_values(instance, values, editable_fields):
                to_update.append((instance, editable_fields))
                if instance.pk in protected_ids:
                    protected_to_recalculate.append(instance)
            else:
                result.unchanged += 1

    if to_create:
        PruebaMuestra.objects.bulk_create(to_create)
        result.created = len(to_create)

    update_groups = {}
    for instance, fields in to_update:
        update_groups.setdefault(tuple(fields), []).append(instance)
    for fields, instances in update_groups.items():
        PruebaMuestra.objects.bulk_update(instances, list(fields))
        result.updated += len(instances)

    if protected_to_recalculate:
        from apps.resultado.api.views.index import _active_result_for, _sync_sample_test_limit_evaluation

        for instance in protected_to_recalculate:
            active_result = _active_result_for(instance)
            if active_result:
                _sync_sample_test_limit_evaluation(instance, active_result)

    result.instances = list(
        PruebaMuestra.objects.filter(
            muestra_id__in=sample_ids,
            prueba_id__in=desired_test_ids,
        ).select_related(
            "muestra",
            "prueba",
            "usuario_solicitud",
            "equipo_configurado",
            "metodo_configurado",
            "condicion_catalogo",
            "condicion_catalogo__unidad",
            "lote_predefinido",
            "criterio_evaluacion",
            "criterio_evaluacion__fuente_limite",
            "criterio_limite_catalogo",
            "criterio_limite_item",
            "criterio_limite_escala",
            "criterio_limite_escala_item",
        )
    )
    return result
