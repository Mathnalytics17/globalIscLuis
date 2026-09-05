from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import json
from django.utils.text import slugify

from apps.misc.api.models.dynamicTechnicalConfig.index import (
    EscalaComparacionItem,
    PruebaFuenteLimite,
    PruebaLimiteCampo,
    normalize_scale_token,
)
from apps.muestras.api.services.evaluation_rules import aggregate_evaluations


@dataclass
class LimitResolution:
    applies: bool
    estado: str
    source: str = None
    catalog: str = None
    item: str = None
    field: str = None
    field_id: int = None
    operator: str = None
    limit_value: str = None
    unit: str = None
    passed: bool = None
    reason: str = None

    def to_dict(self):
        return asdict(self)


@dataclass
class CompositeLimitResolution:
    estado: str
    passed: bool = None
    policy: str = None
    minimum_passed: int = None
    passed_count: int = 0
    evaluated_count: int = 0
    failed_weight: Decimal = Decimal("0")
    critical_failed: list = None
    yellow_count: int = 0
    red_count: int = 0
    yellow_result_count: int = 0
    red_result_count: int = 0
    reason: str = None
    results: list = None
    result_outcomes: list = None

    def to_dict(self):
        data = asdict(self)
        if isinstance(data.get("failed_weight"), Decimal):
            data["failed_weight"] = str(data["failed_weight"])
        return data


def resolve_limit_for_sample_test(prueba_muestra, resultado=None, division=None, componente=None):
    return _resolve_limit(
        prueba_muestra.muestra,
        prueba_muestra.prueba,
        resultado=resultado,
        division=division,
        componente=componente,
        prueba_muestra=prueba_muestra,
    )


def resolve_and_evaluate_sample_test_result(valor, prueba_muestra, resultado=None, division=None, componente=None):
    fields = _matching_limit_fields(prueba_muestra, resultado=resultado, division=division, componente=componente)
    if len(fields) > 1:
        evaluations = [
            _evaluate_entry_with_field(prueba_muestra, {"valor": valor, "field": {}}, field)
            for field in fields
        ]
        return _aggregate_field_evaluations(evaluations, fields[0].fuente_limite)

    resolved = resolve_limit_for_sample_test(prueba_muestra, resultado, division, componente)
    if not resolved.applies:
        return resolved

    field = PruebaLimiteCampo.objects.filter(pk=resolved.field_id).first() if resolved.field_id else None
    evaluation = _status_payload_from_field(valor, field, resolved.limit_value) if field else None
    if evaluation:
        resolved.passed = evaluation["passed"]
        resolved.estado = evaluation["estado"]
        resolved.reason = evaluation["reason"]
    else:
        resolved.passed = _evaluate_resolved(valor, resolved)
        if resolved.passed is None:
            resolved.estado = "NO_EVALUABLE"
            resolved.reason = "El resultado no se pudo comparar con el limite configurado."
        else:
            resolved.estado = "NORMAL" if resolved.passed else "FUERA_DE_LIMITE"
            resolved.reason = "Resultado dentro del limite." if resolved.passed else "Resultado fuera del limite."
    return resolved


def _aggregate_field_evaluations(evaluations, source=None):
    policy = source.politica_evaluacion if source else "todas_deben_cumplir"
    config = source.configuracion_regla if source else {}
    result_rules = source.reglas_resultados if source else {}
    outcome = aggregate_evaluations(
        evaluations,
        policy,
        None,
        config,
        result_rules=result_rules,
    )

    return CompositeLimitResolution(
        estado=outcome.estado,
        passed=outcome.passed,
        policy=policy,
        minimum_passed=None,
        passed_count=outcome.passed_count,
        evaluated_count=outcome.evaluated_count,
        failed_weight=outcome.failed_weight,
        critical_failed=outcome.critical_failed,
        yellow_count=outcome.yellow_count,
        red_count=outcome.red_count,
        yellow_result_count=outcome.yellow_result_count,
        red_result_count=outcome.red_result_count,
        reason=_aggregation_reason(outcome),
        results=evaluations,
        result_outcomes=outcome.result_outcomes,
    )


def _aggregation_reason(outcome):
    if outcome.estado == "CRITICO":
        if outcome.red_result_count:
            return f"{outcome.red_result_count} resultado(s) alcanzaron estado crítico."
        if outcome.red_count:
            return f"{outcome.red_count} campo(s) alcanzaron estado crítico."
        return f"{outcome.yellow_result_count or outcome.yellow_count} resultado(s) en alerta alcanzaron el umbral crítico."
    if outcome.estado == "NO_DESEADO":
        return f"{outcome.yellow_result_count or outcome.yellow_count} resultado(s) quedaron en zona de alerta."
    if outcome.estado == "NORMAL":
        return "Todos los campos evaluables quedaron en zona aceptable."
    return "No fue posible completar la evaluacion tecnica."


def resolve_and_evaluate_values_for_sample_test(prueba_muestra, valores):
    evaluations = []
    for entry in valores:
        fields = _matching_limit_fields(
            prueba_muestra,
            resultado=entry.get("resultado"),
            division=entry.get("division"),
            componente=entry.get("componente"),
        )
        if not fields:
            evaluations.append(resolve_and_evaluate_sample_test_result(
                entry.get("valor"),
                prueba_muestra,
                resultado=entry.get("resultado"),
                division=entry.get("division"),
                componente=entry.get("componente"),
            ).to_dict())
            continue

        for field in fields:
            evaluations.append(_evaluate_entry_with_field(prueba_muestra, entry, field))

    source_ids = {item.get("source") for item in evaluations if item.get("source")}
    source = (
        PruebaFuenteLimite.objects.filter(pk=next(iter(source_ids))).first()
        if len(source_ids) == 1
        else None
    )
    return _aggregate_field_evaluations(evaluations, source)
def resolve_limit_for_result(muestra, prueba, resultado=None, division=None, componente=None):
    return _resolve_limit(
        muestra,
        prueba,
        resultado=resultado,
        division=division,
        componente=componente,
    )


def resolve_and_evaluate_result(valor, muestra, prueba, resultado=None, division=None, componente=None):
    resolved = resolve_limit_for_result(muestra, prueba, resultado, division, componente)
    if not resolved.applies:
        return resolved

    field = PruebaLimiteCampo.objects.filter(pk=getattr(resolved, "field_id", None)).first() if getattr(resolved, "field_id", None) else None
    if field:
        evaluation = _status_payload_from_field(valor, field, resolved.limit_value)
        resolved.passed = evaluation["passed"]
        resolved.estado = evaluation["estado"]
        resolved.reason = evaluation["reason"]
    else:
        resolved.passed = _evaluate_resolved(valor, resolved)
        if resolved.passed is None:
            resolved.estado = "NO_EVALUABLE"
            resolved.reason = "El resultado no se pudo comparar con el límite configurado."
        else:
            resolved.estado = "NORMAL" if resolved.passed else "FUERA_DE_LIMITE"
            resolved.reason = "Resultado dentro del límite." if resolved.passed else "Resultado fuera del límite."
    return resolved


def resolve_and_evaluate_composite_result(valores, muestra, prueba):
    """Evalúa el conjunto de componentes de una prueba según la política configurada."""
    evaluations = []
    for entry in valores:
        resolved = resolve_and_evaluate_result(
            entry.get("valor"),
            muestra,
            prueba,
            resultado=entry.get("resultado"),
            division=entry.get("division"),
            componente=entry.get("componente"),
        )
        payload = resolved.to_dict()
        result = entry.get("resultado")
        payload["result_id"] = getattr(result, "id", result)
        payload["result_label"] = getattr(result, "nombre", None)
        evaluations.append(payload)
    sources = {
        evaluation.get("source")
        for evaluation in evaluations
        if evaluation.get("source")
    }
    source = (
        PruebaFuenteLimite.objects.filter(pk=next(iter(sources))).first()
        if len(sources) == 1
        else None
    )
    return _aggregate_field_evaluations(
        evaluations,
        source,
    )


def _best_limit_field(source, resultado=None, division=None, componente=None):
    queryset = PruebaLimiteCampo.objects.filter(
        fuente_limite=source,
        activo=True,
        deleted_at__isnull=True,
    )
    if componente:
        exact = queryset.filter(componente=componente).first()
        if exact:
            return exact
    if division:
        exact = queryset.filter(componente__isnull=True, division=division).first()
        if exact:
            return exact
    if resultado:
        exact = queryset.filter(
            componente__isnull=True,
            division__isnull=True,
            resultado=resultado,
        ).first()
        if exact:
            return exact
    return queryset.filter(
        componente__isnull=True,
        division__isnull=True,
        resultado__isnull=True,
    ).first()


def _resolve_limit(muestra, prueba, resultado=None, division=None, componente=None, prueba_muestra=None):
    sources = (
        PruebaFuenteLimite.objects
        .filter(prueba=prueba, activo=True, deleted_at__isnull=True)
        .select_related("catalogo_fuente")
        .order_by("prioridad", "id")
    )

    has_sources = False
    missing_technical_information = False

    for source in sources:
        has_sources = True
        if getattr(source, "tipo_limite", "catalogo") == "sin_limite":
            return LimitResolution(
                applies=False,
                estado="SIN_LIMITE",
                source=str(source.id),
                reason="La prueba esta configurada sin limite.",
            )

        field = _best_limit_field(source, resultado, division, componente)
        if not field:
            continue

        if getattr(source, "tipo_limite", "catalogo") == "global":
            configured_value = _global_limit_value_for_field(field, prueba_muestra)
            if configured_value in [None, ""] and not getattr(field, "evaluacion_opciones", None):
                continue
            if configured_value in [None, ""] and getattr(field, "evaluacion_opciones", None):
                configured_value = "__EVALUACION_POR_VALOR__"
            return LimitResolution(
                applies=True,
                estado="PENDIENTE_EVALUACION",
                source=str(source.id),
                field=field.codigo,
                field_id=field.id,
                operator=field.operador,
                limit_value=configured_value,
                unit=field.unidad,
                reason=_global_limit_reason(field, prueba_muestra),
            )

        criterion = _criterion_for_source(source, prueba_muestra)
        criterion_value = _criterion_limit_value_for_field(criterion, field)
        if criterion_value not in [None, ""]:
            return LimitResolution(
                applies=True,
                estado="PENDIENTE_EVALUACION",
                source=str(source.id),
                catalog=source.catalogo_fuente.codigo if source.catalogo_fuente_id else None,
                item=str(getattr(criterion, "catalogo_item_id", None) or getattr(prueba_muestra, "criterio_limite_item_id", None) or ""),
                field=field.codigo,
                field_id=field.id,
                operator=field.operador,
                limit_value=criterion_value,
                unit=field.unidad,
                reason=f"Limite resuelto desde el criterio {criterion.nombre}.",
            )

        item, _ = _criterion_item_for_source(muestra, source, prueba_muestra)
        if not item:
            missing_technical_information = True
            continue
        criterion = _criterion_for_item(source, item)
        criterion_value = _criterion_limit_value_for_field(criterion, field)
        if criterion_value not in [None, ""]:
            return LimitResolution(
                applies=True,
                estado="PENDIENTE_EVALUACION",
                source=str(source.id),
                catalog=source.catalogo_fuente.codigo if source.catalogo_fuente_id else None,
                item=str(item.id),
                field=field.codigo,
                field_id=field.id,
                operator=field.operador,
                limit_value=criterion_value,
                unit=field.unidad,
                reason=f"Limite resuelto desde el criterio {criterion.nombre}.",
            )

    if missing_technical_information:
        return LimitResolution(
            applies=False,
            estado="SIN_INFORMACION_TECNICA",
            reason="Falta informaciÃ³n tÃ©cnica de la muestra o criterio de lÃ­mite de la prueba asignada.",
        )
    if has_sources:
        return LimitResolution(
            applies=False,
            estado="SIN_LIMITE_CONFIGURADO",
            reason="La asociaciÃ³n existe, pero no hay un lÃ­mite configurado para este resultado.",
        )
    return LimitResolution(
        applies=False,
        estado="SIN_LIMITE",
        reason="La prueba no tiene una fuente de lÃ­mite configurada.",
    )


def _criterion_item_for_source(muestra, source, prueba_muestra=None):
    if (
        prueba_muestra
        and getattr(prueba_muestra, "criterio_limite_item_id", None)
        and prueba_muestra.criterio_limite_item.catalogo_id == source.catalogo_fuente_id
    ):
        return (
            prueba_muestra.criterio_limite_item,
            "LÃ­mite resuelto desde el criterio seleccionado en la asignaciÃ³n de la prueba.",
        )

    attributes = muestra.atributos_tecnicos.select_related("item", "campo_tecnico", "catalogo")
    if getattr(source, "tipo_limite", "catalogo") == "campo_muestra" and getattr(source, "campo_tecnico_muestra_id", None):
        attribute = attributes.filter(campo_tecnico=source.campo_tecnico_muestra).first()
    else:
        attribute = attributes.filter(catalogo=source.catalogo_fuente).first()
    if attribute and not attribute.desconocido and attribute.item_id:
        label = getattr(attribute.campo_tecnico, "nombre_visible", None) or getattr(attribute.catalogo, "nombre", None)
        if label:
            return attribute.item, f"Limite resuelto desde la muestra: {label}."
        return attribute.item, "LÃ­mite resuelto desde la configuraciÃ³n tÃ©cnica de la muestra."
    return None, None


def _criterion_for_source(source, prueba_muestra=None):
    if not prueba_muestra:
        return None

    selected = getattr(prueba_muestra, "criterio_evaluacion", None)
    if selected and selected.fuente_limite_id == source.id:
        return selected

    assigned_item = getattr(prueba_muestra, "criterio_limite_item", None)
    candidates = source.criterios.filter(activo=True, deleted_at__isnull=True)
    if assigned_item:
        direct = candidates.filter(catalogo_item=assigned_item).first()
        if direct:
            return direct
        assigned_labels = {
            _normalize_text(getattr(assigned_item, "nombre", None)),
            _normalize_text(getattr(assigned_item, "codigo", None)),
        }
        for candidate in candidates:
            labels = {
                _normalize_text(candidate.nombre),
                _normalize_text(candidate.codigo),
                _normalize_text(candidate.valor),
            }
            if assigned_labels & labels:
                return candidate

    sample_item, _ = _criterion_item_for_source(prueba_muestra.muestra, source, None)
    if sample_item:
        direct = candidates.filter(catalogo_item=sample_item).first()
        if direct:
            return direct
        sample_labels = {
            _normalize_text(getattr(sample_item, "nombre", None)),
            _normalize_text(getattr(sample_item, "codigo", None)),
        }
        for candidate in candidates:
            labels = {
                _normalize_text(candidate.nombre),
                _normalize_text(candidate.codigo),
                _normalize_text(candidate.valor),
            }
            if sample_labels & labels:
                return candidate

    assigned_value = getattr(prueba_muestra, "criterio_limite_valor", None)
    if assigned_value not in [None, ""]:
        assigned_text = _normalize_text(assigned_value)
        for candidate in candidates:
            if assigned_text in {
                _normalize_text(candidate.nombre),
                _normalize_text(candidate.codigo),
                _normalize_text(candidate.valor),
            }:
                return candidate

    return None


def _criterion_for_item(source, item):
    if not item:
        return None
    candidates = source.criterios.filter(activo=True, deleted_at__isnull=True)
    direct = candidates.filter(catalogo_item=item).first()
    if direct:
        return direct
    item_labels = {
        _normalize_text(getattr(item, "nombre", None)),
        _normalize_text(getattr(item, "codigo", None)),
    }
    for candidate in candidates:
        labels = {
            _normalize_text(candidate.nombre),
            _normalize_text(candidate.codigo),
            _normalize_text(candidate.valor),
        }
        if item_labels & labels:
            return candidate
    return None


def _criterion_limit_value_for_field(criterion, field):
    if not criterion:
        return None
    values = criterion.valores_limite if isinstance(criterion.valores_limite, dict) else {}
    for key in [field.codigo, str(field.id), f"field_{field.id}"]:
        if key and values.get(key) not in [None, ""]:
            return values.get(key)
    return criterion.valor if not values else None


def _field_rule_config(field):
    source = getattr(field, "fuente_limite", None)
    config = getattr(source, "configuracion_regla", None) if source else None
    if not isinstance(config, dict):
        return {}
    fields = config.get("campos") if isinstance(config.get("campos"), list) else []
    for item in fields:
        if str(item.get("codigo") or "") == str(getattr(field, "codigo", "")):
            return item
        if (
            str(item.get("componente") or "") == str(getattr(field, "componente_id", "") or "")
            and str(item.get("resultado") or "") == str(getattr(field, "resultado_id", "") or "")
        ):
            return item
    return {}


def _global_limit_value_for_field(field, prueba_muestra=None):
    origin = _field_rule_config(field).get("origen_limite")
    selected_criterion = getattr(prueba_muestra, "criterio_evaluacion", None)
    if origin in [None, "", "catalogo"] and selected_criterion and selected_criterion.fuente_limite_id == field.fuente_limite_id:
        criterion_value = _criterion_limit_value_for_field(selected_criterion, field)
        if criterion_value not in [None, ""]:
            return criterion_value
    assigned_value = getattr(prueba_muestra, "criterio_limite_valor", None)
    field_value = _assigned_limit_value_for_field(assigned_value, field)
    if origin in [None, "", "asignacion", "directo", "escala", "booleano"] and field_value not in [None, ""]:
        return field_value
    scale_item = getattr(prueba_muestra, "criterio_limite_escala_item", None)
    if (
        origin in [None, "", "asignacion", "directo", "escala", "booleano"]
        and
        scale_item
        and getattr(field, "tipo_comparacion", None) in ["escala", "escala_ordinal"]
        and scale_item.escala_id == getattr(field, "escala_comparacion_id", None)
    ):
        return scale_item.etiqueta
    return field.valor_global


def _global_limit_reason(field, prueba_muestra=None):
    origin = _field_rule_config(field).get("origen_limite")
    selected_criterion = getattr(prueba_muestra, "criterio_evaluacion", None)
    if origin in [None, "", "catalogo"] and selected_criterion and selected_criterion.fuente_limite_id == field.fuente_limite_id:
        return f"Límite resuelto desde el criterio {selected_criterion.nombre}."
    assigned_value = getattr(prueba_muestra, "criterio_limite_valor", None)
    if origin in [None, "", "asignacion", "directo", "escala", "booleano"] and _assigned_limit_value_for_field(assigned_value, field) not in [None, ""]:
        return "Limite resuelto desde el criterio seleccionado en la asignacion."
    scale_item = getattr(prueba_muestra, "criterio_limite_escala_item", None)
    if (
        origin in [None, "", "asignacion", "directo", "escala", "booleano"]
        and
        scale_item
        and getattr(field, "tipo_comparacion", None) in ["escala", "escala_ordinal"]
        and scale_item.escala_id == getattr(field, "escala_comparacion_id", None)
    ):
        return "Limite resuelto desde el criterio de escala seleccionado en la asignacion."
    return "Limite global configurado para la prueba."


def _assigned_limit_value_for_field(assigned_value, field):
    if assigned_value in [None, ""]:
        return None

    parsed = assigned_value
    source_field_count = lambda: PruebaLimiteCampo.objects.filter(
        fuente_limite=getattr(field, "fuente_limite", None),
        activo=True,
        deleted_at__isnull=True,
    ).count()

    if isinstance(assigned_value, str):
        try:
            parsed = json.loads(assigned_value)
        except (TypeError, ValueError):
            return assigned_value if source_field_count() <= 1 else None

    if isinstance(parsed, dict):
        candidates = [
            str(getattr(field, "id", "")),
            getattr(field, "codigo", None),
            f"field_{getattr(field, 'id', '')}",
        ]
        nested = parsed.get("fields") if isinstance(parsed.get("fields"), dict) else None
        for source in [parsed, nested]:
            if not source:
                continue
            for key in candidates:
                if key and source.get(key) not in [None, ""]:
                    return source.get(key)
        return None

    return parsed if source_field_count() <= 1 else None


def _matching_limit_fields(prueba_muestra, resultado=None, division=None, componente=None):
    fields = []
    sources = PruebaFuenteLimite.objects.filter(
        prueba=prueba_muestra.prueba,
        activo=True,
        deleted_at__isnull=True,
    ).order_by("prioridad", "id")
    for source in sources:
        is_global = getattr(source, "tipo_limite", "catalogo") == "global"
        if getattr(source, "tipo_limite", "catalogo") == "sin_limite":
            continue
        item, _ = _criterion_item_for_source(prueba_muestra.muestra, source, prueba_muestra)
        criterion = _criterion_for_source(source, prueba_muestra)
        if not is_global and not item and not criterion:
            continue
        queryset = PruebaLimiteCampo.objects.filter(
            fuente_limite=source,
            activo=True,
            deleted_at__isnull=True,
        ).select_related("resultado", "division", "componente").order_by("orden", "id")
        candidates = []
        if componente:
            candidates = list(queryset.filter(componente=componente))
        if not candidates and division:
            candidates = list(queryset.filter(componente__isnull=True, division=division))
        if not candidates and resultado:
            candidates = list(queryset.filter(componente__isnull=True, division__isnull=True, resultado=resultado))
        if not candidates:
            candidates = list(queryset.filter(componente__isnull=True, division__isnull=True, resultado__isnull=True))
        if componente:
            matched = [field for field in candidates if _field_matches_component(field, componente)]
            candidates = matched or candidates
        fields.extend(candidates)
    return fields



def _status_payload_from_field(value, field, configured_value):
    semaphore = _evaluate_semaphore_rule(value, field, configured_value)
    if semaphore is not None:
        return semaphore
    if configured_value not in [None, "", "__EVALUACION_POR_VALOR__"]:
        passed = _evaluate_typed(value, field, configured_value)
        if passed is not None:
            return {
                "passed": passed,
                "estado": "NORMAL" if passed else "FUERA_DE_LIMITE",
                "reason": "Resultado dentro del límite." if passed else "Resultado fuera del límite.",
            }

    mapped = _mapped_evaluation(value, field)
    if mapped:
        return mapped

    passed = _evaluate_typed(value, field, configured_value)
    if passed is None:
        return {
            "passed": None,
            "estado": "NO_EVALUABLE",
            "reason": "El resultado no se pudo comparar con el límite configurado.",
        }
    return {
        "passed": passed,
        "estado": "NORMAL" if passed else "FUERA_DE_LIMITE",
        "reason": "Resultado dentro del límite." if passed else "Resultado fuera del límite.",
    }


def _parse_rule(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip().startswith("{"):
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _rule_value(rule, key):
    value = rule.get(key)
    return None if value in [None, ""] else value


def _evaluate_semaphore_rule(value, field, configured_value):
    rule = _parse_rule(configured_value)
    if not rule:
        return None

    expected = _rule_value(rule, "valor_esperado")
    if expected is not None:
        passed = _evaluate_typed(value, field, expected)
        if passed is None:
            return {"passed": None, "estado": "NO_EVALUABLE", "reason": "El valor no se pudo comparar con el esperado."}
        return {
            "passed": passed,
            "estado": "NORMAL" if passed else "CRITICO",
            "reason": "Valor esperado cumplido." if passed else f"Valor distinto al esperado ({expected}).",
        }

    minimum_ok = _rule_value(rule, "min_aceptable")
    maximum_ok = _rule_value(rule, "max_aceptable")
    minimum_critical = _rule_value(rule, "min_critico")
    maximum_critical = _rule_value(rule, "max_critico")
    if all(item is None for item in [minimum_ok, maximum_ok, minimum_critical, maximum_critical]):
        return None

    if getattr(field, "tipo_comparacion", None) in ["escala", "escala_ordinal"]:
        minimum_ok_match = True if minimum_ok is None else _evaluate_scale_threshold(value, field, minimum_ok, "min")
        maximum_ok_match = True if maximum_ok is None else _evaluate_scale_threshold(value, field, maximum_ok, "max")
        if minimum_ok_match is None or maximum_ok_match is None:
            return {"passed": None, "estado": "NO_EVALUABLE", "reason": "El valor no pertenece a la escala configurada."}
        if minimum_ok_match and maximum_ok_match:
            return {"passed": True, "estado": "NORMAL", "reason": "Valor dentro del intervalo aceptable de la escala."}
        if not rule.get("usar_amarillo"):
            return {"passed": False, "estado": "CRITICO", "reason": "Valor de escala fuera del intervalo aceptable."}

        below_critical = (
            minimum_critical is not None
            and _evaluate_scale_threshold(value, field, minimum_critical, "min") is False
        )
        above_critical = (
            maximum_critical is not None
            and _evaluate_scale_threshold(value, field, maximum_critical, "max") is False
        )
        if not below_critical and not above_critical:
            return {"passed": False, "estado": "NO_DESEADO", "reason": "Valor de escala dentro de la zona amarilla."}
        return {"passed": False, "estado": "CRITICO", "reason": "Valor de escala en zona critica."}

    try:
        actual = Decimal(str(value))
        minimum_ok_number = Decimal(str(minimum_ok)) if minimum_ok is not None else None
        maximum_ok_number = Decimal(str(maximum_ok)) if maximum_ok is not None else None
        minimum_critical_number = Decimal(str(minimum_critical)) if minimum_critical is not None else None
        maximum_critical_number = Decimal(str(maximum_critical)) if maximum_critical is not None else None
    except (InvalidOperation, TypeError, ValueError):
        return {"passed": None, "estado": "NO_EVALUABLE", "reason": "El resultado o sus limites no son numericos."}

    within_ok = (
        (minimum_ok_number is None or actual >= minimum_ok_number)
        and (maximum_ok_number is None or actual <= maximum_ok_number)
    )
    if within_ok:
        return {"passed": True, "estado": "NORMAL", "reason": "Resultado dentro del intervalo aceptable."}
    if not rule.get("usar_amarillo"):
        return {"passed": False, "estado": "CRITICO", "reason": "Resultado fuera del intervalo aceptable."}

    below_critical = minimum_critical_number is not None and actual < minimum_critical_number
    above_critical = maximum_critical_number is not None and actual > maximum_critical_number
    if below_critical or above_critical:
        return {"passed": False, "estado": "CRITICO", "reason": "Resultado fuera del intervalo critico."}
    return {"passed": False, "estado": "NO_DESEADO", "reason": "Resultado dentro de la zona amarilla."}


def _evaluate_scale_threshold(value, field, limit_value, operator):
    value_item = _find_scale_item(getattr(field, "escala_comparacion_id", None), value)
    limit_item = _find_scale_item(getattr(field, "escala_comparacion_id", None), limit_value)
    if not value_item or not limit_item:
        return None
    attr = "numero_base" if getattr(field, "modo_ordinal", "orden") == "numero_base" else "orden"
    left = getattr(value_item, attr)
    right = getattr(limit_item, attr)
    if left is None or right is None:
        return None
    return left <= right if operator == "max" else left >= right


def _mapped_evaluation(value, field):
    mapping = getattr(field, "evaluacion_opciones", None)
    if not isinstance(mapping, dict) or not mapping:
        return None

    keys = [
        _normalize_text(value),
        normalize_scale_token(value),
        str(value or "").strip(),
    ]
    # Alias booleanos para que "Sí", "si", "true", "1" puedan mapear de forma robusta.
    bool_value = _parse_bool(value)
    if bool_value is True:
        keys.extend(["si", "sí", "true", "1", "yes", "presente"])
    elif bool_value is False:
        keys.extend(["no", "false", "0", "ausente"])

    candidate = None
    for key in keys:
        if key in mapping:
            candidate = mapping.get(key)
            break

    if candidate is None:
        return None

    if isinstance(candidate, str):
        estado = _normalize_estado(candidate)
        label = candidate
    elif isinstance(candidate, dict):
        estado = _normalize_estado(candidate.get("estado") or candidate.get("status") or candidate.get("valor"))
        label = candidate.get("label") or candidate.get("comentario") or candidate.get("estado") or estado
    else:
        return None

    return {
        "passed": _passed_from_estado(estado),
        "estado": estado,
        "reason": f"Evaluación configurada por valor: {label or estado}.",
    }


def _normalize_estado(value):
    text = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    aliases = {
        "NO_DESEADO": "FUERA_DE_LIMITE",
        "FUERA_DE_LIMITE": "FUERA_DE_LIMITE",
        "FUERA_LIMITE": "FUERA_DE_LIMITE",
        "ALERTA": "FUERA_DE_LIMITE",
        "NORMAL": "NORMAL",
        "OK": "NORMAL",
        "CUMPLE": "NORMAL",
        "NO_EVALUABLE": "NO_EVALUABLE",
        "N_E": "NO_EVALUABLE",
        "INFORMATIVO": "INFORMATIVO",
        "SIN_LIMITE": "SIN_LIMITE",
    }
    return aliases.get(text, text or "NO_EVALUABLE")


def _passed_from_estado(estado):
    if estado == "NORMAL":
        return True
    if estado in ["FUERA_DE_LIMITE"]:
        return False
    return None


def _evaluate_entry_with_field(prueba_muestra, entry, field):
    rule_config = _field_rule_config(field)
    origin = rule_config.get("origen_limite") or ("global" if getattr(field.fuente_limite, "tipo_limite", "catalogo") == "global" else "catalogo")
    selected_criterion = getattr(prueba_muestra, "criterio_evaluacion", None)
    if origin == "catalogo" and selected_criterion and selected_criterion.fuente_limite_id == field.fuente_limite_id:
        configured_value = _criterion_limit_value_for_field(selected_criterion, field)
        if configured_value not in [None, ""]:
            evaluation = _status_payload_from_field(entry.get("valor"), field, configured_value)
            payload_field = entry.get("field") or {}
            return {
                "applies": True,
                "estado": evaluation["estado"],
                "source": str(field.fuente_limite_id),
                "field": field.codigo,
                "field_id": field.id,
                "field_label": payload_field.get("label") or payload_field.get("componente_nombre") or field.nombre,
                "result_id": payload_field.get("resultado_id"),
                "result_label": payload_field.get("resultado_nombre"),
                "operator": field.operador,
                "limit_value": configured_value,
                "unit": field.unidad,
                "passed": evaluation["passed"],
                "reason": evaluation["reason"],
                "resolution_reason": f"Límite resuelto desde el criterio {selected_criterion.nombre}.",
            }
    if origin == "asignacion":
        configured_value = _assigned_limit_value_for_field(getattr(prueba_muestra, "criterio_limite_valor", None), field)
        if configured_value in [None, ""]:
            return LimitResolution(
                applies=False,
                estado="SIN_LIMITE_CONFIGURADO",
                source=str(field.fuente_limite_id),
                field=field.codigo,
                field_id=field.id,
                operator=field.operador,
                unit=field.unidad,
                reason="Este campo espera un limite capturado en la asignacion.",
            ).to_dict()
        evaluation = _status_payload_from_field(entry.get("valor"), field, configured_value)
        payload_field = entry.get("field") or {}
        return {
            "applies": True,
            "estado": evaluation["estado"],
            "source": str(field.fuente_limite_id),
            "field": field.codigo,
            "field_id": field.id,
            "field_label": payload_field.get("label") or payload_field.get("componente_nombre") or field.nombre,
            "result_id": payload_field.get("resultado_id"),
            "result_label": payload_field.get("resultado_nombre"),
            "operator": field.operador,
            "limit_value": configured_value,
            "unit": field.unidad,
            "passed": evaluation["passed"],
            "reason": evaluation["reason"],
            "resolution_reason": "Limite resuelto desde la asignacion de la prueba.",
        }

    if origin in ["directo", "escala", "booleano"] or getattr(field.fuente_limite, "tipo_limite", "catalogo") == "global":
        configured_value = _global_limit_value_for_field(field, prueba_muestra)
        if configured_value in [None, ""] and not getattr(field, "evaluacion_opciones", None):
            return LimitResolution(
                applies=False,
                estado="SIN_LIMITE_CONFIGURADO",
                source=str(field.fuente_limite_id),
                field=field.codigo,
                field_id=field.id,
                operator=field.operador,
                unit=field.unidad,
                reason="La asociacion global existe, pero no hay un valor configurado.",
            ).to_dict()

        if configured_value in [None, ""] and getattr(field, "evaluacion_opciones", None):
            configured_value = "__EVALUACION_POR_VALOR__"

        evaluation = _status_payload_from_field(entry.get("valor"), field, configured_value)
        passed = evaluation["passed"]
        estado = evaluation["estado"]
        reason = evaluation["reason"]

        payload_field = entry.get("field") or {}
        return {
            "applies": True,
            "estado": estado,
            "source": str(field.fuente_limite_id),
            "field": field.codigo,
            "field_id": field.id,
            "field_label": payload_field.get("label") or payload_field.get("componente_nombre") or field.nombre,
            "result_id": payload_field.get("resultado_id"),
            "result_label": payload_field.get("resultado_nombre"),
            "operator": field.operador,
            "limit_value": configured_value,
            "unit": field.unidad,
            "passed": passed,
            "reason": reason,
            "resolution_reason": _global_limit_reason(field, prueba_muestra),
        }

    criterion = _criterion_for_source(field.fuente_limite, prueba_muestra)
    criterion_value = _criterion_limit_value_for_field(criterion, field)
    if criterion_value not in [None, ""]:
        evaluation = _status_payload_from_field(entry.get("valor"), field, criterion_value)
        payload_field = entry.get("field") or {}
        assigned_item = getattr(prueba_muestra, "criterio_limite_item", None)
        return {
            "applies": True,
            "estado": evaluation["estado"],
            "source": str(field.fuente_limite_id),
            "catalog": field.fuente_limite.catalogo_fuente.codigo if field.fuente_limite.catalogo_fuente_id else None,
            "catalog_label": field.fuente_limite.catalogo_fuente.nombre if field.fuente_limite.catalogo_fuente_id else None,
            "item": str(getattr(criterion, "catalogo_item_id", None) or getattr(prueba_muestra, "criterio_limite_item_id", None) or ""),
            "item_label": getattr(getattr(criterion, "catalogo_item", None), "nombre", None) or getattr(assigned_item, "nombre", None) or getattr(criterion, "nombre", None),
            "field": field.codigo,
            "field_id": field.id,
            "field_label": payload_field.get("label") or payload_field.get("componente_nombre") or field.nombre,
            "result_id": payload_field.get("resultado_id"),
            "result_label": payload_field.get("resultado_nombre"),
            "operator": field.operador,
            "limit_value": criterion_value,
            "unit": field.unidad,
            "passed": evaluation["passed"],
            "reason": evaluation["reason"],
            "resolution_reason": f"Limite resuelto desde el criterio {criterion.nombre}.",
        }

    item, _ = _criterion_item_for_source(prueba_muestra.muestra, field.fuente_limite, prueba_muestra)
    return LimitResolution(
        applies=False,
        estado="SIN_LIMITE_CONFIGURADO" if item else "SIN_INFORMACION_TECNICA",
        source=str(field.fuente_limite_id),
        catalog=field.fuente_limite.catalogo_fuente.codigo if field.fuente_limite.catalogo_fuente_id else None,
        item=str(item.id) if item else None,
        field=field.codigo,
        field_id=field.id,
        operator=field.operador,
        unit=field.unidad,
        reason="Configure un criterio de evaluacion con valores_limite para este campo.",
    ).to_dict()


def _field_matches_component(field, componente):
    if not componente:
        return False
    token = (getattr(componente, "acronimo", None) or getattr(componente, "nombre", None) or "").strip().lower()
    if not token:
        return False
    for value in [field.codigo or "", field.nombre or ""]:
        normalized = str(value).lower().replace("-", "_").replace(" ", "_")
        parts = [part for part in normalized.split("_") if part]
        if token in parts or normalized.endswith(f"_{token}") or normalized == token:
            return True
    return False


def _evaluate_resolved(value, resolved):
    if getattr(resolved, "field_id", None):
        field = PruebaLimiteCampo.objects.filter(pk=resolved.field_id).first()
        if field:
            return _evaluate_typed(value, field, resolved.limit_value)
    return _evaluate(value, resolved.operator, resolved.limit_value)


def _evaluate(value, operator, limit_value):
    operator = operator or "eq"
    if operator == "informativo":
        return None

    try:
        value_dec = Decimal(str(value).replace(",", "."))
        limit_dec = Decimal(str(limit_value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        value_text = _normalize_text(value)
        limit_text = _normalize_text(limit_value)
        if operator == "eq":
            return value_text == limit_text
        if operator == "neq":
            return value_text != limit_text
        if operator in ["in", "not_in"]:
            values = _split_values(limit_value)
            result = value_text in values
            return result if operator == "in" else not result
        return None

    if operator in ["max", "warn_max"]:
        return value_dec <= limit_dec
    if operator in ["min", "warn_min"]:
        return value_dec >= limit_dec
    if operator == "eq":
        return value_dec == limit_dec
    if operator == "neq":
        return value_dec != limit_dec
    return None


def _evaluate_typed(value, field, limit_value):
    comparison_type = getattr(field, "tipo_comparacion", None) or "numerica"
    operator = field.operador or "eq"

    if comparison_type == "informativo" or operator == "informativo":
        return None

    if comparison_type == "booleano":
        value_bool = _parse_bool_for_field(value, field)
        limit_bool = _parse_bool_for_field(limit_value, field)
        if value_bool is None or limit_bool is None:
            return None
        return value_bool == limit_bool if operator != "neq" else value_bool != limit_bool

    if comparison_type in ["opcion", "texto"]:
        value_text = _normalize_text(value)
        if operator in ["in", "not_in"]:
            values = _split_values(limit_value)
            result = value_text in values
            return result if operator == "in" else not result
        if operator == "neq":
            return value_text != _normalize_text(limit_value)
        return value_text == _normalize_text(limit_value)

    if comparison_type in ["escala", "escala_ordinal"]:
        value_item = _find_scale_item(getattr(field, "escala_comparacion_id", None), value)
        limit_item = _find_scale_item(getattr(field, "escala_comparacion_id", None), limit_value)
        if not value_item or not limit_item:
            return None
        attr = "numero_base" if getattr(field, "modo_ordinal", "orden") == "numero_base" else "orden"
        left = getattr(value_item, attr)
        right = getattr(limit_item, attr)
        if left is None or right is None:
            return None
        if operator in ["max", "scale_max", "warn_max"]:
            return left <= right
        if operator in ["min", "scale_min", "warn_min"]:
            return left >= right
        if operator == "neq":
            return left != right
        return left == right

    return _evaluate(value, operator, limit_value)


def _normalize_text(value):
    return str(value or "").strip().casefold()


def _split_values(value):
    if isinstance(value, (list, tuple, set)):
        return {_normalize_text(item) for item in value}
    return {
        _normalize_text(item)
        for item in str(value or "").replace(";", ",").replace("|", ",").split(",")
        if str(item).strip()
    }


def _parse_bool_for_field(value, field=None):
    parsed = _parse_bool(value)
    if parsed is not None:
        return parsed
    component = getattr(field, "componente", None) if field else None
    true_label = _normalize_text(getattr(component, "etiqueta_verdadero", None))
    false_label = _normalize_text(getattr(component, "etiqueta_falso", None))
    text = _normalize_text(value)
    if true_label and text == true_label:
        return True
    if false_label and text == false_label:
        return False
    return None


def _parse_bool(value):
    text = _normalize_text(value)
    if text in ["true", "1", "si", "sÃ­", "sí", "yes", "y", "pasa", "presente", "hay"]:
        return True
    if text in ["false", "0", "no", "n", "no pasa", "ausente", "no hay"]:
        return False
    return None


def _find_scale_item(scale_id, value):
    if not scale_id or value in [None, ""]:
        return None
    normalized = normalize_scale_token(value)
    return (
        EscalaComparacionItem.objects
        .filter(escala_id=scale_id, activo=True, deleted_at__isnull=True)
        .filter(valor_normalizado=normalized)
        .first()
        or EscalaComparacionItem.objects
        .filter(escala_id=scale_id, activo=True, deleted_at__isnull=True, etiqueta__iexact=str(value).strip())
        .first()
    )
