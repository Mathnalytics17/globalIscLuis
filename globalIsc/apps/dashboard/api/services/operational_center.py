from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.reporte.api.models.index import Reporte
from apps.users.api.models.index import User


CLOSED_BATCH_STATES = {"reportado", "cancelado"}
ACTIVE_BATCH_STATES = {"borrador", "registrado", "recibido", "en_laboratorio", "en_analisis", "parcial", "resultados_completos", "revisado"}

# These groups reflect the actual `LoteMuestras.estado` state machine.  A lot
# has dates for shipping and reception, but it does not yet persist a
# timestamp for every state transition.  The dashboard consequently reports
# exact shipping time and *days since reception* for the later stages instead
# of inventing a stage-entry date.
OPERATIONAL_STAGES = {
    "shipping": {"label": "En envío", "states": {"borrador", "registrado"}},
    "received": {"label": "Recibidas", "states": {"recibido", "en_laboratorio"}},
    "analysis": {"label": "En análisis", "states": {"en_analisis", "parcial", "resultados_completos"}},
    "approval": {"label": "Pendientes de aprobación", "states": {"revisado"}},
}

STATUS_LABELS = {
    "borrador": "Borrador",
    "registrado": "Registrado",
    "recibido": "Recibido",
    "en_laboratorio": "En laboratorio",
    "en_analisis": "En analisis",
    "parcial": "Parcial",
    "resultados_completos": "Resultados completos",
    "revisado": "Revisado",
    "reportado": "Reportado",
    "cancelado": "Cancelado",
}

ACTION_BY_STATE = {
    "borrador": ("Completar lote", "/muestras/lotes/{id}/editar"),
    "registrado": ("Ingresar a laboratorio", "/muestras/laboratorio?lote={id}"),
    "recibido": ("Ingresar a laboratorio", "/muestras/laboratorio?lote={id}"),
    "en_laboratorio": ("Asignar pruebas", "/muestras/asignacion-pruebas?lote={id}"),
    "en_analisis": ("Ingresar resultados", "/muestras/resultados?lote={id}"),
    "parcial": ("Completar resultados", "/muestras/resultados?lote={id}"),
    "resultados_completos": ("Revisar resultados", "/muestras/revision-resultados?lote={id}"),
    "revisado": ("Interpretar", "/muestras/interpretacion?lote={id}"),
    "reportado": ("Ver reportes", "/reportes?lote={id}"),
}

def scoped_batches_for_user(user):
    queryset = LoteMuestras.objects.select_related("cliente_empresa", "tipo_gestion", "usuario_registro").prefetch_related("muestras")
    if not user or not user.is_authenticated:
        return queryset.none()
    if user.is_superuser or user.role in [User.Role.GLOBAL, User.Role.LABORATORISTA]:
        return queryset
    return queryset.filter(cliente_empresa=user.empresa)


def _base_date(batch):
    """The service commitment starts when the laboratory receives the lot."""
    return batch.fecha_recepcion


def _add_business_days(start, days):
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def _business_days_between(start, end):
    if start == end:
        return 0
    step = 1 if end > start else -1
    current = start
    count = 0
    while current != end:
        current += timedelta(days=step)
        if current.weekday() < 5:
            count += step
    return count


def due_info_for_batch(batch, today=None):
    today = today or timezone.localdate()
    management = batch.tipo_gestion
    if not management:
        return {
            "base_date": None,
            "due_date": None,
            "days_remaining": None,
            "day_mode": "sin_sla",
            "sla_days": None,
            "urgency": "sin_sla",
            "label": "Sin SLA",
        }

    business_days = int(getattr(management, "dias_habiles", 0) or 0)
    calendar_days = int(getattr(management, "dias_calendario", 0) or 0)
    base = _base_date(batch)
    if not base and (business_days > 0 or calendar_days > 0):
        return {
            "base_date": None,
            "due_date": None,
            "days_remaining": None,
            "day_mode": "pendiente_recepcion",
            "sla_days": business_days or calendar_days,
            "urgency": "pendiente_recepcion",
            "label": "SLA inicia al recibir en laboratorio",
        }

    if business_days > 0:
        due_date = _add_business_days(base, business_days)
        remaining = _business_days_between(today, due_date)
        mode = "habiles"
        sla_days = business_days
    elif calendar_days > 0:
        due_date = base + timedelta(days=calendar_days)
        remaining = (due_date - today).days
        mode = "calendario"
        sla_days = calendar_days
    else:
        return {
            "base_date": base,
            "due_date": None,
            "days_remaining": None,
            "day_mode": "sin_sla",
            "sla_days": None,
            "urgency": "sin_sla",
            "label": "Sin SLA",
        }

    if batch.estado in CLOSED_BATCH_STATES:
        urgency = "cerrado"
        label = "Cerrado"
    elif remaining < 0:
        urgency = "vencido"
        label = f"Vencido hace {abs(remaining)} dia(s)"
    elif remaining == 0:
        urgency = "vence_hoy"
        label = "Vence hoy"
    elif remaining <= 2:
        urgency = "proximo"
        label = f"Vence en {remaining} dia(s)"
    else:
        urgency = "normal"
        label = f"{remaining} dia(s)"

    return {
        "base_date": base,
        "due_date": due_date,
        "days_remaining": remaining,
        "day_mode": mode,
        "sla_days": sla_days,
        "urgency": urgency,
        "label": label,
    }


def _client_name(batch):
    return getattr(batch.cliente_empresa, "nombre", None) or batch.cliente_ocasional_nombre or "Sin cliente"


def _batch_progress(batch):
    samples = list(batch.muestras.all())
    total = len(samples)
    entered = sum(1 for item in samples if item.is_ingresado)
    results = sum(1 for item in samples if item.is_resultado_ingresado)
    reviewed = sum(1 for item in samples if item.is_revisado)
    percentage = round((results / total) * 100) if total else 0
    return {
        "total_samples": total,
        "entered_samples": entered,
        "result_samples": results,
        "reviewed_samples": reviewed,
        "percentage": percentage,
        "label": f"{results}/{total} con resultados" if total else "0/0",
    }


def serialize_batch_card(batch, today=None):
    due = due_info_for_batch(batch, today=today)
    action_label, action_href = ACTION_BY_STATE.get(batch.estado, ("Ver lote", "/muestras/lotes/{id}"))
    progress = _batch_progress(batch)
    return {
        "id": batch.id,
        "client": _client_name(batch),
        "management_type": getattr(batch.tipo_gestion, "nombre", None) or "Sin gestion",
        "status": batch.estado,
        "status_label": STATUS_LABELS.get(batch.estado, batch.estado),
        "received_date": batch.fecha_recepcion,
        "sent_date": batch.fecha_envio,
        "registered_at": batch.fecha_registro,
        "due": due,
        "progress": progress,
        "contact_name": batch.contacto_nombre,
        "contact_email": batch.contacto_email,
        "action": {
            "label": action_label,
            "href": action_href.format(id=batch.id),
        },
    }


def _month_key(value):
    if not value:
        return "Sin fecha"
    if isinstance(value, datetime):
        value = timezone.localtime(value).date()
    return f"{value.year}-{str(value.month).zfill(2)}"


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _apply_operational_filters(queryset, params, today):
    """Filter at the database boundary so dashboard aggregates share scope."""
    client = params.get("cliente") or params.get("empresa")
    management = params.get("tipo_gestion") or params.get("gestion")
    if client:
        queryset = queryset.filter(cliente_empresa_id=client)
    if management:
        queryset = queryset.filter(tipo_gestion_id=management)

    start = _parse_date(params.get("fecha_desde"))
    end = _parse_date(params.get("fecha_hasta"))
    period = str(params.get("periodo") or "").lower()
    if not start and not end:
        if period == "dia":
            start = end = today
        elif period == "mes":
            start = today.replace(day=1)
            next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
            end = next_month - timedelta(days=1)
        elif period in {"ano", "año", "year"}:
            start, end = date(today.year, 1, 1), date(today.year, 12, 31)
    if start:
        queryset = queryset.filter(fecha_envio__gte=start)
    if end:
        queryset = queryset.filter(fecha_envio__lte=end)
    return queryset, {"cliente": str(client or ""), "tipo_gestion": str(management or ""), "fecha_desde": start, "fecha_hasta": end, "periodo": period or "todos"}


def _operational_stage(batch):
    for key, definition in OPERATIONAL_STAGES.items():
        if batch.estado in definition["states"]:
            return key
    return None


def _days_since(value, today):
    if not value:
        return None
    return max(0, (today - value).days)


def _build_stage_metrics(batches, today):
    grouped = {key: [] for key in OPERATIONAL_STAGES}
    for batch in batches:
        stage = _operational_stage(batch)
        if stage:
            grouped[stage].append(batch)

    metrics = []
    for key, definition in OPERATIONAL_STAGES.items():
        items = grouped[key]
        if key == "shipping":
            values = [_days_since(item.fecha_envio, today) for item in items]
            time_label = "Promedio de días en envío"
        else:
            values = [_days_since(item.fecha_recepcion, today) for item in items]
            time_label = "Promedio de días desde recepción"
        known = [value for value in values if value is not None]
        metrics.append({
            "key": key,
            "label": definition["label"],
            "count": len(items),
            "average_days": round(sum(known) / len(known), 1) if known else None,
            "time_label": time_label,
        })
    return metrics


def _serialize_operational_delay(batch, today):
    stage = _operational_stage(batch)
    if not stage:
        return None
    stage_definition = OPERATIONAL_STAGES[stage]
    stage_date = batch.fecha_envio if stage == "shipping" else batch.fecha_recepcion
    days = _days_since(stage_date, today)
    return {
        "id": batch.id,
        "client": _client_name(batch),
        "management_type": getattr(batch.tipo_gestion, "nombre", None) or "Sin gestión",
        # A row represents a batch.  A raw machine foreign-key here produced
        # values such as "4" and "2" under the misleading header "Equipo".
        "sample_count": len(batch.muestras.all()),
        "stage": stage,
        "stage_label": stage_definition["label"],
        "stage_date": stage_date,
        "days_in_stage": days,
        "time_label": "Días en envío" if stage == "shipping" else "Días desde recepción",
        "severity": "alta" if (days or 0) >= 10 else "media" if (days or 0) >= 5 else "normal",
        "action": ACTION_BY_STATE.get(batch.estado, ("Ver lote", "/muestras/lotes/{id}"))[1].format(id=batch.id),
    }


def build_operational_center(user, params=None):
    params = params or {}
    today = timezone.localdate()
    base_queryset, applied_filters = _apply_operational_filters(scoped_batches_for_user(user), params, today)
    batches = list(base_queryset.all())
    active_batches = [item for item in batches if item.estado not in CLOSED_BATCH_STATES]
    serialized = [serialize_batch_card(item, today=today) for item in active_batches]

    overdue = [item for item in serialized if item["due"]["urgency"] == "vencido"]
    due_today = [item for item in serialized if item["due"]["urgency"] == "vence_hoy"]
    due_soon = [item for item in serialized if item["due"]["urgency"] == "proximo"]
    ready = [item for item in serialized if item["status"] in ["resultados_completos", "revisado"]]
    new_today = [item for item in batches if timezone.localtime(item.fecha_registro).date() == today]

    scoped_batch_ids = [item.id for item in batches]
    tests_qs = PruebaMuestra.objects.filter(muestra__lote_id__in=scoped_batch_ids, estado_asignacion="confirmada")
    total_tests = tests_qs.count()
    completed_tests = tests_qs.filter(completada=True).count()
    reviewed_tests = tests_qs.filter(is_revisada=True).count()
    undesired_tests = tests_qs.filter(
        Q(estado_limite__icontains="NO DESEADO")
        | Q(estado_limite__icontains="FUERA")
        | Q(estado_limite__icontains="CRIT")
        | Q(evaluacion_limite__estado__in=["FUERA_DE_LIMITE", "NO_DESEADO", "CRITICO"])
    )
    config_issue_tests = tests_qs.filter(
        Q(estado_limite__icontains="NO EVALUABLE")
        | Q(estado_limite__icontains="SIN LIMITE")
        | Q(estado_limite__icontains="SIN_LIMITE")
        | Q(estado_limite__icontains="SIN INFO")
    )
    reports_qs = Reporte.objects.filter(lote_id__in=scoped_batch_ids)
    report_ready = reports_qs.filter(estatus__in=["generado", "aprobado"], fecha_envio__isnull=True).count()
    sent_today = reports_qs.filter(fecha_envio__date=today).count()

    alerts = []
    for item in overdue[:10]:
        alerts.append(_alert("overdue", "alta", f"{item['id']} vencido", f"{item['client']} - {item['due']['label']}", item))
    for item in due_today[:10]:
        alerts.append(_alert("due_today", "alta", f"{item['id']} vence hoy", f"{item['client']} - {item['status_label']}", item))
    for item in due_soon[:10]:
        alerts.append(_alert("due_soon", "media", f"{item['id']} proximo a entrega", f"{item['client']} - {item['due']['label']}", item))
    for item in ready[:10]:
        alerts.append(_alert("ready", "media", f"{item['id']} listo para informe", f"{item['client']} - {item['status_label']}", item))

    for test in undesired_tests.select_related("muestra", "muestra__lote", "prueba").order_by("-fecha_medicion")[:10]:
        batch = test.muestra.lote
        card = serialize_batch_card(batch, today=today)
        alerts.append(_alert(
            "undesired_result",
            "alta",
            f"Resultado no deseado en {batch.id}",
            f"{test.prueba.acronimo} - {test.muestra_id}",
            card,
        ))

    for test in config_issue_tests.select_related("muestra", "muestra__lote", "prueba").order_by("-fecha_medicion")[:8]:
        batch = test.muestra.lote
        card = serialize_batch_card(batch, today=today)
        alerts.append(_alert(
            "config_issue",
            "media",
            f"Resultado no evaluable en {batch.id}",
            f"{test.prueba.acronimo} - {test.estado_limite or 'Sin detalle'}",
            card,
        ))

    by_status = Counter(item.estado for item in batches)
    by_management = Counter(getattr(item.tipo_gestion, "nombre", None) or "Sin gestion" for item in batches)
    monthly = defaultdict(lambda: {"created": 0, "reported": 0})
    for batch in batches:
        monthly[_month_key(batch.fecha_registro)]["created"] += 1
        if batch.estado == "reportado":
            monthly[_month_key(batch.fecha_actualizacion)]["reported"] += 1

    stage_metrics = _build_stage_metrics(batches, today)
    delayed_samples = [item for item in (_serialize_operational_delay(batch, today) for batch in active_batches) if item]
    delayed_samples.sort(key=lambda item: (item["days_in_stage"] is None, -(item["days_in_stage"] or 0), item["id"]))
    received_days = [_days_since(batch.fecha_recepcion, today) for batch in active_batches if batch.fecha_recepcion]
    client_options = sorted({
        (str(batch.cliente_empresa_id), _client_name(batch))
        for batch in scoped_batches_for_user(user).exclude(cliente_empresa__isnull=True)
    }, key=lambda item: item[1].lower())
    management_options = sorted({
        (str(batch.tipo_gestion_id), getattr(batch.tipo_gestion, "nombre", None) or "Sin gestión")
        for batch in scoped_batches_for_user(user).exclude(tipo_gestion__isnull=True)
    }, key=lambda item: item[1].lower())

    return {
        "generated_at": timezone.now(),
        "today": today,
        "filters": {
            "applied": applied_filters,
            "clients": [{"id": key, "label": label} for key, label in client_options],
            "management_types": [{"id": key, "label": label} for key, label in management_options],
            "periods": ["dia", "mes", "ano"],
        },
        "operational": {
            "stages": stage_metrics,
            "average_process_days": round(sum(received_days) / len(received_days), 1) if received_days else None,
            "average_process_label": "Promedio desde recepción",
            "analysis_count": completed_tests,
            "analysis_label": "Pruebas con resultado confirmado",
            "delayed_samples": delayed_samples[:50],
            "time_note": "El sistema registra envío y recepción. No registra aún la fecha de cada cambio de etapa; por eso las etapas posteriores muestran días desde recepción.",
        },
        "summary": {
            "active_batches": len(active_batches),
            "new_today": len(new_today),
            "overdue": len(overdue),
            "due_today": len(due_today),
            "due_soon": len(due_soon),
            "ready": len(ready),
            "undesired_results": undesired_tests.count(),
            "config_issues": config_issue_tests.count(),
            "report_ready": report_ready,
            "reports_sent_today": sent_today,
            "tests_total": total_tests,
            "tests_completed": completed_tests,
            "tests_reviewed": reviewed_tests,
        },
        "queues": {
            "priority": sorted(serialized, key=lambda item: _queue_sort_key(item))[:30],
            "overdue": overdue,
            "due_today": due_today,
            "due_soon": due_soon,
            "ready": ready,
        },
        "alerts": alerts[:40],
        "history": {
            "by_status": [{"label": STATUS_LABELS.get(key, key), "value": value} for key, value in by_status.items()],
            "by_management": [{"label": key, "value": value} for key, value in by_management.items()],
            "monthly": [{"month": key, **value} for key, value in sorted(monthly.items())[-12:]],
        },
    }


def _queue_sort_key(item):
    urgency_rank = {"vencido": 0, "vence_hoy": 1, "proximo": 2, "normal": 3, "sin_sla": 4, "cerrado": 5}
    due_date = item["due"].get("due_date") or date.max
    return (urgency_rank.get(item["due"].get("urgency"), 9), due_date, item["id"])


def _alert(kind, severity, title, detail, batch_card):
    return {
        "kind": kind,
        "severity": severity,
        "title": title,
        "detail": detail,
        "batch": batch_card,
        "action": batch_card.get("action"),
    }


