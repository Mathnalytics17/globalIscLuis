import json
import re

from django.db import transaction

from apps.misc.api.models.dynamicTechnicalConfig.index import PruebaFuenteLimite
from apps.misc.api.models.lotesPruebasPredefinidos.index import LotePruebasPredefinidoDetalle
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra


BOUNDARY_KEYS = {
    "min_critico",
    "min_aceptable",
    "max_aceptable",
    "max_critico",
    "valor_esperado",
    "usar_amarillo",
}


def parse_json_value(value):
    parsed = value
    for _ in range(3):
        if not isinstance(parsed, str) or not parsed.strip().startswith(("{", "[")):
            break
        try:
            parsed = json.loads(parsed)
        except (TypeError, ValueError):
            break
    return parsed


def _is_blank(value):
    return value is None or value == ""


def _first_value(*values):
    return next((value for value in values if not _is_blank(value)), "")


def _canonical_scale_value(field, value):
    if _is_blank(value) or not getattr(field, "escala_comparacion_id", None):
        return value
    token = str(value).strip().casefold()
    for item in field.escala_comparacion.items.filter(activo=True, deleted_at__isnull=True):
        if token in {
            str(item.id).casefold(),
            str(item.etiqueta or "").strip().casefold(),
            str(item.valor_normalizado or "").strip().casefold(),
        }:
            return item.valor_normalizado or item.etiqueta
    return value


def canonicalize_field_rule(field, value, configured_default=None):
    parsed = parse_json_value(value)
    default = parse_json_value(configured_default)

    if not isinstance(parsed, dict) and isinstance(default, dict):
        parsed = default
    elif not isinstance(parsed, dict):
        parsed = {"limite": parsed, "valor_esperado": parsed}

    operator = str(getattr(field, "operador", "") or "").lower()
    if operator in {"warn_min", "scale_min"}:
        operator = "min"
    elif operator in {"warn_max", "scale_max"}:
        operator = "max"
    elif operator in {"range", "rango"}:
        operator = "between"

    yellow = bool(parsed.get("usar_amarillo"))
    if operator in {"eq", "neq"}:
        canonical = {
            "valor_esperado": _first_value(parsed.get("valor_esperado"), parsed.get("limite")),
            "usar_amarillo": False,
        }
    elif operator == "min":
        canonical = {
            "min_critico": _first_value(parsed.get("min_critico")),
            "min_aceptable": _first_value(
                parsed.get("min_aceptable"), parsed.get("min"), parsed.get("limite"), parsed.get("valor_esperado")
            ),
            "usar_amarillo": yellow,
        }
    elif operator == "between":
        canonical = {
            "min_critico": _first_value(parsed.get("min_critico")),
            "min_aceptable": _first_value(parsed.get("min_aceptable"), parsed.get("min")),
            "max_aceptable": _first_value(parsed.get("max_aceptable"), parsed.get("max")),
            "max_critico": _first_value(parsed.get("max_critico")),
            "usar_amarillo": yellow,
        }
    else:
        canonical = {
            "max_aceptable": _first_value(
                parsed.get("max_aceptable"), parsed.get("max"), parsed.get("limite"), parsed.get("valor_esperado")
            ),
            "max_critico": _first_value(parsed.get("max_critico")),
            "usar_amarillo": yellow,
        }

    if getattr(field, "tipo_comparacion", None) in {"escala", "escala_ordinal"}:
        canonical = {
            key: (_canonical_scale_value(field, item) if key != "usar_amarillo" else item)
            for key, item in canonical.items()
        }
    return canonical


def _field_config(source, field):
    fields = source.configuracion_regla.get("campos", []) if isinstance(source.configuracion_regla, dict) else []
    for item in fields:
        if str(item.get("codigo") or "") == str(field.codigo or ""):
            return item
        if (
            str(item.get("componente") or "") == str(field.componente_id or "")
            and str(item.get("resultado") or "") == str(field.resultado_id or "")
        ):
            return item
    return {}


def _current_contract(prueba):
    sources = list(
        PruebaFuenteLimite.objects.filter(
            prueba=prueba,
            activo=True,
            deleted_at__isnull=True,
        ).prefetch_related("campos_limite")
    )
    fields = []
    for source in sources:
        for field in source.campos_limite.filter(activo=True, deleted_at__isnull=True):
            config = _field_config(source, field)
            origin = config.get("origen_limite") or (
                "directo" if source.tipo_limite == "global" else "catalogo"
            )
            fields.append((source, field, config, origin))
    return sources, fields


def _value_for_field(values, field):
    if not isinstance(values, dict):
        return None
    for key in (str(field.id), field.codigo, f"field_{field.id}"):
        if key and key in values:
            return values[key]
    # Older builders inserted extra separators in generated field codes
    # (for example iso_4_6_14 versus iso_4614). Preserve that value while
    # rewriting it under the current canonical code.
    canonical_code = re.sub(r"[^a-z0-9]", "", str(field.codigo or "").casefold())
    if canonical_code:
        for key, value in values.items():
            if re.sub(r"[^a-z0-9]", "", str(key).casefold()) == canonical_code:
                return value
    return None


def _serialized_contract_for_assignment(assignment, fields, *, reset_direct_defaults):
    raw = parse_json_value(assignment.criterio_limite_valor)
    if not isinstance(raw, dict):
        raw = {}

    normalized = {}
    for _source, field, config, origin in fields:
        if origin not in {"asignacion", "directo", "escala", "booleano"}:
            continue

        configured = parse_json_value(config.get("valor_global"))
        if _is_blank(configured):
            configured = parse_json_value(field.valor_global)
        current = _value_for_field(raw, field)
        if reset_direct_defaults and origin in {"directo", "escala", "booleano"} and not _is_blank(configured):
            current = configured
        if _is_blank(current) and not _is_blank(configured):
            current = configured
        if _is_blank(current):
            continue

        normalized[str(field.id)] = canonicalize_field_rule(field, current, configured)

    return json.dumps(normalized, ensure_ascii=False, sort_keys=True) if normalized else None


def _recalculate_assignment(assignment):
    from apps.resultado.api.views.index import _active_result_for, _sync_sample_test_limit_evaluation

    result = _active_result_for(assignment)
    if result:
        _sync_sample_test_limit_evaluation(assignment, result)


@transaction.atomic
def reconcile_test_assignments(prueba, *, reset_direct_defaults=False, dry_run=False):
    sources, fields = _current_contract(prueba)
    source_ids = {source.id for source in sources}
    has_catalog = any(source.tipo_limite in {"catalogo", "campo_muestra", "seleccion_asignacion"} for source in sources)
    has_scale = any(field.tipo_comparacion in {"escala", "escala_ordinal"} for _source, field, _config, _origin in fields)
    changes = []

    for assignment in PruebaMuestra.objects.filter(prueba=prueba).select_related("prueba", "criterio_evaluacion"):
        before = {
            "criterio_evaluacion_id": assignment.criterio_evaluacion_id,
            "criterio_limite_catalogo_id": assignment.criterio_limite_catalogo_id,
            "criterio_limite_item_id": assignment.criterio_limite_item_id,
            "criterio_limite_escala_id": assignment.criterio_limite_escala_id,
            "criterio_limite_escala_item_id": assignment.criterio_limite_escala_item_id,
            "criterio_limite_valor": assignment.criterio_limite_valor,
        }

        assignment.criterio_limite_valor = _serialized_contract_for_assignment(
            assignment,
            fields,
            reset_direct_defaults=reset_direct_defaults,
        )
        if assignment.criterio_evaluacion_id and assignment.criterio_evaluacion.fuente_limite_id not in source_ids:
            assignment.criterio_evaluacion_id = None
        if not has_catalog:
            assignment.criterio_evaluacion_id = None
            assignment.criterio_limite_catalogo_id = None
            assignment.criterio_limite_item_id = None
        if not has_scale:
            assignment.criterio_limite_escala_id = None
            assignment.criterio_limite_escala_item_id = None

        after = {
            "criterio_evaluacion_id": assignment.criterio_evaluacion_id,
            "criterio_limite_catalogo_id": assignment.criterio_limite_catalogo_id,
            "criterio_limite_item_id": assignment.criterio_limite_item_id,
            "criterio_limite_escala_id": assignment.criterio_limite_escala_id,
            "criterio_limite_escala_item_id": assignment.criterio_limite_escala_item_id,
            "criterio_limite_valor": assignment.criterio_limite_valor,
        }
        if before == after:
            continue

        changes.append({
            "assignment": assignment.id,
            "sample": assignment.muestra_id,
            "test": assignment.prueba.acronimo,
            "before": before,
            "after": after,
        })
        if not dry_run:
            assignment.save(update_fields=[
                "criterio_evaluacion",
                "criterio_limite_catalogo",
                "criterio_limite_item",
                "criterio_limite_escala",
                "criterio_limite_escala_item",
                "criterio_limite_valor",
            ])
            _recalculate_assignment(assignment)

    return changes


def reconcile_all_assignments(*, reset_direct_defaults=False, dry_run=False):
    changes = []
    test_ids = PruebaFuenteLimite.objects.filter(
        activo=True,
        deleted_at__isnull=True,
    ).values_list("prueba_id", flat=True).distinct()
    for prueba_id in test_ids:
        changes.extend(reconcile_test_assignments(
            prueba_id,
            reset_direct_defaults=reset_direct_defaults,
            dry_run=dry_run,
        ))
    return changes


@transaction.atomic
def reconcile_test_predefined_details(prueba, *, reset_direct_defaults=False, dry_run=False):
    """Keep reusable batches aligned when a test changes its limit source."""
    sources, fields = _current_contract(prueba)
    has_catalog = any(
        source.tipo_limite in {"catalogo", "campo_muestra", "seleccion_asignacion"}
        for source in sources
    )
    has_scale = any(
        field.tipo_comparacion in {"escala", "escala_ordinal"}
        for _source, field, _config, _origin in fields
    )
    changes = []

    for detail in LotePruebasPredefinidoDetalle.objects.filter(
        prueba=prueba,
        activo=True,
    ).select_related("prueba", "lote"):
        before = {
            "criterio_limite_catalogo_id": detail.criterio_limite_catalogo_id,
            "criterio_limite_item_id": detail.criterio_limite_item_id,
            "criterio_limite_escala_id": detail.criterio_limite_escala_id,
            "criterio_limite_escala_item_id": detail.criterio_limite_escala_item_id,
            "criterio_limite_valor": detail.criterio_limite_valor,
        }

        detail.criterio_limite_valor = _serialized_contract_for_assignment(
            detail,
            fields,
            reset_direct_defaults=reset_direct_defaults,
        )
        if not has_catalog:
            detail.criterio_limite_catalogo_id = None
            detail.criterio_limite_item_id = None
        if not has_scale:
            detail.criterio_limite_escala_id = None
            detail.criterio_limite_escala_item_id = None

        after = {
            "criterio_limite_catalogo_id": detail.criterio_limite_catalogo_id,
            "criterio_limite_item_id": detail.criterio_limite_item_id,
            "criterio_limite_escala_id": detail.criterio_limite_escala_id,
            "criterio_limite_escala_item_id": detail.criterio_limite_escala_item_id,
            "criterio_limite_valor": detail.criterio_limite_valor,
        }
        if before == after:
            continue

        changes.append({
            "detail": detail.id,
            "batch": detail.lote_id,
            "test": detail.prueba.acronimo,
            "before": before,
            "after": after,
        })
        if not dry_run:
            detail.save(update_fields=[
                "criterio_limite_catalogo",
                "criterio_limite_item",
                "criterio_limite_escala",
                "criterio_limite_escala_item",
                "criterio_limite_valor",
            ])

    return changes


def reconcile_all_predefined_details(*, reset_direct_defaults=False, dry_run=False):
    changes = []
    test_ids = PruebaFuenteLimite.objects.filter(
        activo=True,
        deleted_at__isnull=True,
    ).values_list("prueba_id", flat=True).distinct()
    for prueba_id in test_ids:
        changes.extend(reconcile_test_predefined_details(
            prueba_id,
            reset_direct_defaults=reset_direct_defaults,
            dry_run=dry_run,
        ))
    return changes


@transaction.atomic
def reconcile_definition_contracts(*, dry_run=False):
    changes = []
    sources = PruebaFuenteLimite.objects.filter(
        activo=True,
        deleted_at__isnull=True,
    ).prefetch_related("campos_limite", "criterios")

    for source in sources:
        fields = [
            field for field in source.campos_limite.all()
            if field.activo and field.deleted_at is None
        ]
        configs = source.configuracion_regla.get("campos", []) if isinstance(source.configuracion_regla, dict) else []
        config_by_code = {
            str(item.get("codigo")): item for item in configs if item.get("codigo")
        }

        source_changed = False
        for field in fields:
            config = config_by_code.get(str(field.codigo), {})
            origin = config.get("origen_limite") or (
                "directo" if source.tipo_limite == "global" else "catalogo"
            )
            if origin not in {"directo", "escala", "booleano"}:
                continue
            configured = parse_json_value(config.get("valor_global"))
            if _is_blank(configured):
                configured = parse_json_value(field.valor_global)
            if _is_blank(configured):
                continue
            canonical = canonicalize_field_rule(field, configured)
            serialized = json.dumps(canonical, ensure_ascii=False, sort_keys=True)
            if field.valor_global != serialized:
                changes.append({
                    "type": "field",
                    "id": field.id,
                    "test": source.prueba.acronimo,
                    "before": field.valor_global,
                    "after": serialized,
                })
                if not dry_run:
                    field.valor_global = serialized
                    field.save(update_fields=["valor_global", "updated_at"])
            if config.get("valor_global") != canonical:
                config["valor_global"] = canonical
                source_changed = True

        if source_changed:
            changes.append({
                "type": "source",
                "id": source.id,
                "test": source.prueba.acronimo,
                "before": "non-canonical direct values",
                "after": "canonical semaphore rules",
            })
            if not dry_run:
                source.configuracion_regla = {**source.configuracion_regla, "campos": configs}
                source.save(update_fields=["configuracion_regla", "updated_at"])

        for criterion in source.criterios.all():
            if not criterion.activo or criterion.deleted_at is not None:
                continue
            current_values = criterion.valores_limite if isinstance(criterion.valores_limite, dict) else {}
            normalized = {}
            for field in fields:
                config = config_by_code.get(str(field.codigo), {})
                origin = config.get("origen_limite") or (
                    "directo" if source.tipo_limite == "global" else "catalogo"
                )
                if origin != "catalogo":
                    continue
                value = _value_for_field(current_values, field)
                if _is_blank(value):
                    continue
                normalized[field.codigo] = canonicalize_field_rule(field, value)
            if normalized == current_values:
                continue
            changes.append({
                "type": "criterion",
                "id": criterion.id,
                "test": source.prueba.acronimo,
                "before": current_values,
                "after": normalized,
            })
            if not dry_run:
                criterion.valores_limite = normalized
                criterion.save(update_fields=["valores_limite", "updated_at"])

    return changes
