from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.utils import timezone

from apps.dashboard.models import NotificationDispatchLog, NotificationTopic
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.reporte.api.models.index import Reporte
from apps.users.api.models.index import User


CLOSED_BATCH_STATES = {"reportado", "cancelado"}
ACTIVE_BATCH_STATES = {"borrador", "registrado", "recibido", "en_laboratorio", "en_analisis", "parcial", "resultados_completos", "revisado"}

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
    if user.is_superuser or user.role in [User.Role.GLOBAL, User.Role.ADMIN, User.Role.LABORATORISTA]:
        return queryset
    return queryset.filter(cliente_empresa=user.empresa)


def _base_date(batch):
    value = batch.fecha_recepcion or batch.fecha_envio
    if value:
        return value
    return timezone.localtime(batch.fecha_registro).date()


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
    base = _base_date(batch)
    if not base or not management:
        return {
            "base_date": base,
            "due_date": None,
            "days_remaining": None,
            "day_mode": "sin_sla",
            "sla_days": None,
            "urgency": "sin_sla",
            "label": "Sin SLA",
        }

    business_days = int(getattr(management, "dias_habiles", 0) or 0)
    calendar_days = int(getattr(management, "dias_calendario", 0) or 0)

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


def build_operational_center(user, params=None):
    params = params or {}
    today = timezone.localdate()
    batches = list(scoped_batches_for_user(user).all())
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

    return {
        "generated_at": timezone.now(),
        "today": today,
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


def recipients_for_topic(topic):
    return topic.resolved_recipient_emails()


def send_topic_email(code, subject, message, payload=None):
    topic = NotificationTopic.objects.filter(code=code, active=True, email_enabled=True).first()
    if not topic:
        return {"sent": False, "reason": "topic_disabled", "recipients": []}

    recipients = recipients_for_topic(topic)
    if not recipients:
        NotificationDispatchLog.objects.create(
            topic=topic,
            event_code=code,
            subject=subject,
            recipients=[],
            status="skipped",
            payload=payload or {},
            error="Sin destinatarios configurados.",
        )
        return {"sent": False, "reason": "no_recipients", "recipients": []}

    status = "sent"
    error = ""
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
        topic.last_sent_at = timezone.now()
        topic.save(update_fields=["last_sent_at", "updated_at"])
    except Exception as exc:
        status = "failed"
        error = str(exc)

    NotificationDispatchLog.objects.create(
        topic=topic,
        event_code=code,
        subject=subject,
        message=message,
        recipients=recipients,
        status=status,
        attempts=1,
        error=error,
        payload=payload or {},
        processed_at=timezone.now(),
    )
    return {"sent": status == "sent", "status": status, "error": error, "recipients": recipients}


def queue_topic_email(code, subject, message, payload=None):
    topic = NotificationTopic.objects.filter(code=code, active=True, email_enabled=True).first()
    if not topic:
        return {"queued": False, "reason": "topic_disabled", "recipients": []}

    recipients = recipients_for_topic(topic)
    status = "pending" if recipients else "skipped"
    log = NotificationDispatchLog.objects.create(
        topic=topic,
        event_code=code,
        subject=subject,
        message=message,
        recipients=recipients,
        status=status,
        error="" if recipients else "Sin destinatarios configurados.",
        payload=payload or {},
    )
    return {
        "queued": status == "pending",
        "status": status,
        "log_id": log.id,
        "recipients": recipients,
    }


def process_pending_notifications(limit=50):
    pending_ids = list(
        NotificationDispatchLog.objects.filter(status="pending")
        .order_by("created_at")
        .values_list("id", flat=True)[:limit]
    )
    summary = {"processed": 0, "sent": 0, "failed": 0}
    for log_id in pending_ids:
        log = NotificationDispatchLog.objects.select_related("topic").get(pk=log_id)
        log.attempts += 1
        log.processed_at = timezone.now()
        try:
            send_mail(
                log.subject,
                log.message,
                settings.DEFAULT_FROM_EMAIL,
                log.recipients,
                fail_silently=False,
            )
            log.status = "sent"
            log.error = ""
            summary["sent"] += 1
            if log.topic:
                log.topic.last_sent_at = log.processed_at
                log.topic.save(update_fields=["last_sent_at", "updated_at"])
        except Exception as exc:
            log.status = "failed"
            log.error = str(exc)
            summary["failed"] += 1
        log.save(update_fields=["attempts", "processed_at", "status", "error"])
        summary["processed"] += 1
    return summary


def build_daily_digest_message(center):
    summary = center["summary"]
    lines = [
        "Resumen operativo diario",
        "",
        f"Lotes activos: {summary['active_batches']}",
        f"Nuevos hoy: {summary['new_today']}",
        f"Vencidos: {summary['overdue']}",
        f"Vencen hoy: {summary['due_today']}",
        f"Proximos a vencer: {summary['due_soon']}",
        f"Listos para informe: {summary['ready']}",
        f"Resultados no deseados: {summary['undesired_results']}",
        "",
        "Acciones sugeridas:",
    ]
    for item in center["queues"]["priority"][:8]:
        lines.append(f"- {item['id']} - {item['client']} - {item['due']['label']} - {item['action']['label']}")
    return "\n".join(lines)


def send_daily_digest(user):
    center = build_operational_center(user)
    today = timezone.localdate()
    subject = f"Resumen operativo diario - Global Oil - {today:%d/%m/%Y}"
    message = build_daily_digest_message(center)
    return send_topic_email(NotificationTopic.EventCode.DAILY_DIGEST, subject, message, {"summary": center["summary"]})


def send_due_batches_digest(user, code):
    """Send the configured daily delivery warning to its own recipient list."""
    queue_key = {
        NotificationTopic.EventCode.DUE_SOON: "due_soon",
        NotificationTopic.EventCode.OVERDUE: "overdue",
    }.get(code)
    if not queue_key:
        return {"sent": False, "reason": "unsupported_event", "recipients": []}

    center = build_operational_center(user)
    batches = center["queues"][queue_key]
    topic = NotificationTopic.objects.filter(code=code, active=True, email_enabled=True).first()
    if not topic:
        return {"sent": False, "reason": "topic_disabled", "recipients": []}
    if not batches:
        topic.last_sent_at = timezone.now()
        topic.save(update_fields=["last_sent_at", "updated_at"])
        return {"sent": False, "reason": "no_matches", "recipients": topic.resolved_recipient_emails()}

    label = "Lotes próximos a vencer" if code == NotificationTopic.EventCode.DUE_SOON else "Lotes vencidos"
    subject = f"{label} - Global Oil - {timezone.localdate():%d/%m/%Y}"
    lines = [label, ""]
    for item in batches:
        lines.append(
            f"- {item['id']} | {item['client']} | {item['due']['label']} | {item['status_label']}"
        )
    lines.extend(["", "Consulte el centro operativo de Global Oil para ver el detalle."])
    return send_topic_email(code, subject, "\n".join(lines), {"batches": [item["id"] for item in batches]})


def notify_new_batch(batch):
    subject = f"Nuevo lote ingresado - {batch.id}"
    message = "\n".join([
        f"Se ingreso un nuevo lote de muestras: {batch.id}",
        f"Cliente: {_client_name(batch)}",
        f"Tipo de gestion: {getattr(batch.tipo_gestion, 'nombre', None) or 'Sin gestion'}",
        f"Contacto: {batch.contacto_nombre or '-'}",
        f"Correo contacto: {batch.contacto_email or '-'}",
        "",
        f"Ver lote: /muestras/lotes/{batch.id}",
    ])
    return queue_topic_email(
        NotificationTopic.EventCode.NEW_CLIENT_BATCH,
        subject,
        message,
        {"batch_id": batch.id, "client": _client_name(batch)},
    )
