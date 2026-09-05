from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AggregationOutcome:
    estado: str
    passed: bool | None
    passed_count: int
    evaluated_count: int
    failed_weight: Decimal = Decimal("0")
    critical_failed: list | None = None
    yellow_count: int = 0
    red_count: int = 0
    yellow_result_count: int = 0
    red_result_count: int = 0
    result_outcomes: list | None = None


def _value(item, key, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _identifier(item):
    return str(_value(item, "field_id") or _value(item, "field") or _value(item, "field_label") or "")


def _identifiers(item):
    return {
        str(value)
        for value in [
            _value(item, "field_id"),
            _value(item, "field"),
            _value(item, "field_label"),
        ]
        if value not in [None, ""]
    }


def _ignored_fields(config):
    ignored = {
        str(value)
        for value in config.get("informativos", [])
        if value not in [None, ""]
    }
    for item in config.get("campos", []) if isinstance(config.get("campos"), list) else []:
        if not isinstance(item, dict):
            continue
        if item.get("informativo") or item.get("evalua") is False:
            ignored.add(str(item.get("codigo") or ""))
    return ignored


def _flat_outcome(items, policy, config):
    items = list(items or [])
    config = config if isinstance(config, dict) else {}
    ignored = _ignored_fields(config)
    comparable = [
        item for item in items
        if _value(item, "passed") is not None and not (_identifiers(item) & ignored)
    ]
    passed_count = sum(_value(item, "passed") is True for item in comparable)
    yellow_count = sum(_value(item, "estado") == "NO_DESEADO" for item in comparable)
    red_items = [
        item for item in comparable
        if _value(item, "estado") in ["CRITICO", "FUERA_DE_LIMITE"]
    ]
    red_count = len(red_items)

    if any(_value(item, "estado") == "SIN_INFORMACION_TECNICA" for item in items):
        return AggregationOutcome("SIN_INFORMACION_TECNICA", None, passed_count, len(comparable))
    if policy == "solo_informativo":
        return AggregationOutcome("INFORMATIVO", None, passed_count, len(comparable))
    if not comparable:
        return AggregationOutcome("NO_EVALUABLE", None, 0, 0)

    if red_count:
        return AggregationOutcome(
            "CRITICO",
            False,
            passed_count,
            len(comparable),
            critical_failed=[_identifier(item) for item in red_items],
            yellow_count=yellow_count,
            red_count=red_count,
        )
    if yellow_count:
        return AggregationOutcome(
            "NO_DESEADO",
            False,
            passed_count,
            len(comparable),
            yellow_count=yellow_count,
        )

    passed = passed_count == len(comparable)
    return AggregationOutcome(
        "NORMAL" if passed else "CRITICO",
        passed,
        passed_count,
        len(comparable),
        red_count=0 if passed else len(comparable) - passed_count,
    )


def _result_key(item, index):
    result_id = _value(item, "result_id")
    result_label = _value(item, "result_label")
    if result_id not in [None, ""]:
        return f"id:{result_id}", str(result_label or f"Resultado {result_id}")
    if result_label not in [None, ""]:
        return f"label:{result_label}", str(result_label)
    return "ungrouped", "Resultado principal"


def aggregate_evaluations(
    evaluations,
    policy="todas_deben_cumplir",
    minimum=None,
    config=None,
    result_rules=None,
):
    items = list(evaluations or [])
    config = config if isinstance(config, dict) else {}
    if policy == "solo_informativo":
        return _flat_outcome(items, policy, config)
    if any(_value(item, "estado") == "SIN_INFORMACION_TECNICA" for item in items):
        return _flat_outcome(items, policy, config)

    groups = {}
    labels = {}
    for index, item in enumerate(items):
        key, label = _result_key(item, index)
        groups.setdefault(key, []).append(item)
        labels[key] = label

    if not groups:
        return _flat_outcome(items, policy, config)

    result_outcomes = []
    for key, group_items in groups.items():
        outcome = _flat_outcome(group_items, policy, config)
        result_outcomes.append({
            "key": key,
            "result_id": key.split(":", 1)[1] if key.startswith("id:") else None,
            "label": labels[key],
            "estado": outcome.estado,
            "passed": outcome.passed,
            "passed_count": outcome.passed_count,
            "evaluated_count": outcome.evaluated_count,
            "yellow_count": outcome.yellow_count,
            "red_count": outcome.red_count,
        })

    evaluated_results = [
        item for item in result_outcomes
        if item["estado"] not in ["NO_EVALUABLE", "INFORMATIVO"]
    ]
    if not evaluated_results:
        base = _flat_outcome(items, policy, config)
        return AggregationOutcome(**{**base.__dict__, "result_outcomes": result_outcomes})

    red_results = [item for item in evaluated_results if item["estado"] == "CRITICO"]
    yellow_results = [item for item in evaluated_results if item["estado"] == "NO_DESEADO"]
    if red_results:
        estado = "CRITICO"
        passed = False
    elif yellow_results:
        estado = "NO_DESEADO"
        passed = False
    else:
        estado = "NORMAL"
        passed = True

    return AggregationOutcome(
        estado=estado,
        passed=passed,
        passed_count=sum(item["passed_count"] for item in result_outcomes),
        evaluated_count=sum(item["evaluated_count"] for item in result_outcomes),
        critical_failed=[item["key"] for item in red_results],
        yellow_count=sum(item["yellow_count"] for item in result_outcomes),
        red_count=sum(item["red_count"] for item in result_outcomes),
        yellow_result_count=len(yellow_results),
        red_result_count=len(red_results),
        result_outcomes=result_outcomes,
    )
