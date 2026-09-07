import base64
import io
import logging
import os
import uuid
import zipfile
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import HttpResponse
from django.template import Context, Template
from django.template.loader import get_template
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from xhtml2pdf import pisa
from pypdf import PdfReader, PdfWriter
from apps.utils.pagination import StandardResultsSetPagination
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission

from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.reporte.api.models.index import Reporte, ReporteEnvio
from apps.reporte.api.serializers.index import (
    CreateReporteSerializer,
    ReporteSerializer,
    ReporteSummarySerializer,
)
from apps.resultado.api.views.index import _sample_tests_for_lote
from apps.users.api.models.index import User

logger = logging.getLogger(__name__)


def _user_name(user):
    if not user:
        return None
    full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
    return full_name or getattr(user, "email", None) or str(user)


def _interpretation_from_sample(muestra):
    extra = muestra.campos_adicionales or {}
    if not isinstance(extra, dict):
        return {}
    return extra.get("interpretacion", {}) or {}


def _has_interpretation(muestra):
    data = _interpretation_from_sample(muestra)
    return bool(
        data.get("conclusion")
        or data.get("comentario_proveedor")
        or data.get("comentarios_predefinidos")
        or data.get("selected_predefined_comments")
        or data.get("comentarios_manuales")
    )


def _mark_lote_reported_if_ready(lote):
    if not lote:
        return
    active_samples = lote.muestras.filter(estado_operativo="activa")
    total = active_samples.count()
    reported = active_samples.filter(reportes__isnull=False).distinct().count()
    if total and reported == total:
        lote.estado = "reportado"
        update_fields = ["estado"]
        if hasattr(lote, "fecha_actualizacion"):
            update_fields.append("fecha_actualizacion")
        lote.save(update_fields=update_fields)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _format_report_date(value):
    if not value:
        return ""
    try:
        if isinstance(value, str):
            # ISO string
            return value[:10]
        return value.strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def _split_result_for_report(result_text):
    text = str(result_text or "").strip()
    if "·" in text:
        return [part.strip() for part in text.split("·") if part.strip()]
    return [text] if text else ["-"]


def _clean_limit_label(label):
    if isinstance(label, dict):
        return "Límite configurado"
    text = str(label or "").strip()
    if not text:
        return "-"
    if "{" in text and "}" in text:
        return "Límite configurado"
    normalized = text.upper()
    if normalized in ["-", "NO_EVALUABLE", "SIN_LIMITE", "SIN LIMITE", "SIN INFORMACION TECNICA", "SIN_INFORMACION_TECNICA"]:
        return "-"
    replacements = {
        "secuencia_1_ei": "EI",
        "secuencia_1_fi": "FI",
        "secuencia_2_eii": "EII",
        "secuencia_2_fii": "FII",
        "secuencia_3_eiii": "EIII",
        "secuencia_3_fiii": "FIII",
        "ptochispa_ptochispa_valor_minimo": "Punto de chispa",
        "viscosidad_viscosidad_min": "Viscosidad mín.",
        "viscosidad_viscosidad_max": "Viscosidad máx.",
        "viscosidad_viscosidad": "Viscosidad",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _report_comment_class(comment):
    if comment == "CRÍTICO":
        return "critical"
    if comment == "ALERTA":
        return "warning"
    if comment in ["NO EVALUABLE", "SIN EVALUAR", "INFORMATIVO"]:
        return "neutral"
    if comment in ["NORMAL", "ACEPTABLE"]:
        return "normal"
    return "pending"


def _report_status(value, passed=None):
    status = str(value or "").strip().upper().replace(" ", "_")
    if status in ["CRITICO", "CRÍTICO"]:
        return "CRÍTICO"
    if status in ["NO_DESEADO", "FUERA_DE_LIMITE", "ALERTA"]:
        return "ALERTA"
    if status in ["NORMAL", "OK", "ACEPTABLE"]:
        return "ACEPTABLE"
    if status == "INFORMATIVO":
        return "INFORMATIVO"
    if status in [
        "SIN_LIMITE",
        "SIN_LÍMITE",
        "SIN_INFO_TECNICA",
        "SIN_INFORMACION_TECNICA",
        "NO_EVALUABLE",
        "SIN_RESULTADO",
    ]:
        return "SIN EVALUAR"
    if passed is True:
        return "ACEPTABLE"
    if passed is False:
        return "ALERTA"
    return "PENDIENTE"


def _report_operator(operator):
    return {
        "max": "<=",
        "warn_max": "<=",
        "min": ">=",
        "warn_min": ">=",
        "eq": "=",
        "neq": "!=",
        "scale_max": "<=",
        "scale_min": ">=",
    }.get(operator or "", operator or "")


def _report_range(minimum, maximum, unit=""):
    suffix = f" {unit}" if unit else ""
    if minimum not in [None, ""] and maximum not in [None, ""]:
        return f"Entre {minimum}{suffix} y {maximum}{suffix}"
    if minimum not in [None, ""]:
        return f"Desde {minimum}{suffix}"
    if maximum not in [None, ""]:
        return f"Hasta {maximum}{suffix}"
    return ""


def _ordered_gap(start, end):
    if start in [None, ""] or end in [None, ""]:
        return False
    try:
        return Decimal(str(start)) < Decimal(str(end))
    except Exception:
        return str(start) != str(end)


def _report_limit_bands(detail):
    value = detail.get("limit_value")
    unit = detail.get("unit") or ""
    if isinstance(value, dict):
        acceptable = _report_range(value.get("min_aceptable"), value.get("max_aceptable"), unit)
        if not acceptable and value.get("valor_esperado") not in [None, ""]:
            acceptable = f"Debe ser {value['valor_esperado']}{f' {unit}' if unit else ''}"

        warning = []
        suffix = f" {unit}" if unit else ""
        if value.get("usar_amarillo") and _ordered_gap(value.get("min_critico"), value.get("min_aceptable")):
            warning.append(
                f"Desde {value['min_critico']}{suffix} hasta antes de {value['min_aceptable']}{suffix}"
            )
        if value.get("usar_amarillo") and _ordered_gap(value.get("max_aceptable"), value.get("max_critico")):
            warning.append(
                f"Más de {value['max_aceptable']}{suffix} y hasta {value['max_critico']}{suffix}"
            )

        critical = []
        if value.get("min_critico") not in [None, ""]:
            critical.append(f"Menor que {value['min_critico']}{suffix}")
        if value.get("max_critico") not in [None, ""]:
            critical.append(f"Mayor que {value['max_critico']}{suffix}")
        return {
            "acceptable": acceptable or "Configurado",
            "warning": "; o ".join(warning),
            "critical": "; o ".join(critical),
        }

    display_value = detail.get("limit_value_label")
    if display_value in [None, ""]:
        display_value = value
    if display_value in [None, ""]:
        return {"acceptable": "No aplica", "warning": "", "critical": ""}
    suffix = f" {unit}" if unit else ""
    operator = detail.get("operator")
    operator_label = {
        "max": "Hasta",
        "warn_max": "Hasta",
        "scale_max": "Hasta",
        "min": "Desde",
        "warn_min": "Desde",
        "scale_min": "Desde",
        "eq": "Debe ser",
        "neq": "Distinto de",
    }.get(operator, _report_operator(operator))
    return {
        "acceptable": f"{operator_label} {display_value}{suffix}".strip(),
        "warning": "",
        "critical": "",
    }


def _report_recipient_emails(reporte):
    lote = reporte.lote or getattr(reporte.muestra, "lote", None)
    empresa = getattr(lote, "cliente_empresa", None) if lote else None
    emails = []

    # Principal: correo de contacto del lote/muestra cargada por el cliente.
    for value in [
        getattr(lote, "contacto_email", None),
        getattr(empresa, "email", None),
        getattr(empresa, "correo", None),
        getattr(empresa, "contacto_email", None),
    ]:
        if value:
            for item in str(value).replace(";", ",").split(","):
                item = item.strip()
                if item and item not in emails:
                    emails.append(item)
    return emails


def _save_signature_base64(data_url):
    if not data_url:
        return ""
    if not isinstance(data_url, str) or "base64," not in data_url:
        return ""
    try:
        header, encoded = data_url.split("base64,", 1)
        extension = ".png"
        if "jpeg" in header or "jpg" in header:
            extension = ".jpg"
        filename = f"firma_dibujada_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{extension}"
        saved_path = default_storage.save(os.path.join("firmas", filename), io.BytesIO(base64.b64decode(encoded)))
        return getattr(settings, "MEDIA_URL", "/media/") + saved_path
    except Exception:
        logger.exception("No se pudo guardar firma dibujada")
        return ""


def _default_signature_path(user):
    signature = getattr(user, "firma_predeterminada", None)
    return getattr(signature, "name", "") if signature else ""


class ReporteViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "reportes.ver",
        "retrieve": "reportes.ver",
        "dashboard": "reportes.ver_dashboard",
        "create": "reportes.generar",
        "generate_from_interpretation": "reportes.generar",
        "generate_batch_from_interpretation": "reportes.generar",
        "preview_from_interpretation": "reportes.previsualizar",
        "imprimir_reporte": "reportes.descargar_pdf",
        "export_batch": "reportes.descargar_pdf",
        "destroy": "reportes.generar",
        "publish_client": "reportes.publicar_cliente",
        "unpublish_client": "reportes.despublicar_cliente",
        "send_email_report": "reportes.enviar_email",
        "send_batch_email": "reportes.enviar_email",
        "versions": "reportes.ver_versiones",
        "upload_signature": "reportes.subir_firma",
        "aprobar": "reportes.generar",
        "enviar_aprobacion": "reportes.enviar_email",
        "annul": "reportes.generar",
    }
    queryset = Reporte.objects.select_related(
        "muestra",
        "muestra__lote",
        "lote",
        "lote__cliente_empresa",
        "usuario_emision",
        "usuario_aprobacion",
        "usuario_envio",
    ).prefetch_related("envios")

    def get_queryset(self):
        latest_version = (
            Reporte.objects.filter(muestra_id=OuterRef("muestra_id"))
            .order_by("-version")
            .values("version")[:1]
        )
        queryset = self.queryset.annotate(
            ultima_version_value=Subquery(latest_version)
        )
        user = self.request.user

        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            queryset = queryset.filter(lote__cliente_empresa=getattr(user, "empresa", None))
        if getattr(user, "role", None) == "EMPRESA":
            queryset = queryset.filter(
                visible_cliente=True,
            )

        muestra_id = self.request.query_params.get("muestra")
        lote_id = self.request.query_params.get("lote")
        empresa_id = self.request.query_params.get("empresa")
        estado = self.request.query_params.get("estado")
        visible_cliente = self.request.query_params.get("visible_cliente")
        fecha_generacion_desde = self.request.query_params.get("fecha_generacion_desde")
        fecha_generacion_hasta = self.request.query_params.get("fecha_generacion_hasta")
        fecha_envio_desde = self.request.query_params.get("fecha_envio_desde")
        fecha_envio_hasta = self.request.query_params.get("fecha_envio_hasta")
        search = self.request.query_params.get("search")

        if muestra_id:
            queryset = queryset.filter(muestra_id=muestra_id)
        if lote_id:
            queryset = queryset.filter(lote_id=lote_id)
        if empresa_id:
            queryset = queryset.filter(lote__cliente_empresa_id=empresa_id)
        if estado:
            queryset = queryset.filter(estatus=estado)
        if visible_cliente in ["true", "false"]:
            queryset = queryset.filter(visible_cliente=visible_cliente == "true")
        if fecha_generacion_desde:
            queryset = queryset.filter(fecha_generacion__date__gte=fecha_generacion_desde)
        if fecha_generacion_hasta:
            queryset = queryset.filter(fecha_generacion__date__lte=fecha_generacion_hasta)
        if fecha_envio_desde:
            queryset = queryset.filter(fecha_envio__date__gte=fecha_envio_desde)
        if fecha_envio_hasta:
            queryset = queryset.filter(fecha_envio__date__lte=fecha_envio_hasta)
        if search:
            queryset = queryset.filter(
                Q(consecutivo__icontains=search)
                | Q(muestra_id__icontains=search)
                | Q(lote_id__icontains=search)
                | Q(lote__cliente_empresa__nombre__icontains=search)
                | Q(lote__cliente_ocasional_nombre__icontains=search)
            )

        return queryset.distinct()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CreateReporteSerializer
        return ReporteSerializer

    def perform_create(self, serializer):
        now = timezone.now()
        serializer.save(usuario_emision=self.request.user, fecha_emision=now, fecha_generacion=now)

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Los reportes generados no se editan directamente. Modifique la interpretacion y genere una nueva version."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use la acción Anular reporte e indique el motivo. Los reportes no se eliminan."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"], url_path="annul")
    def annul(self, request, pk=None):
        reporte = self.get_object()
        if reporte.estatus == "anulado":
            return Response({"detail": "El reporte ya está anulado."}, status=status.HTTP_409_CONFLICT)
        if reporte.estatus == "enviado" or reporte.fecha_envio or reporte.visible_cliente:
            return Response(
                {"detail": "Un reporte enviado o publicado no se anula directamente. Genere una versión sustitutiva y publíquela."},
                status=status.HTTP_409_CONFLICT,
            )
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return Response({"reason": ["Indique el motivo de anulación."]}, status=status.HTTP_400_BAD_REQUEST)
        reporte.estatus = "anulado"
        reporte.notas_internas = "\n".join(filter(None, [reporte.notas_internas, f"[Anulación] {reason}"]))
        reporte.save(update_fields=["estatus", "notas_internas"])
        return Response({"detail": "Reporte anulado."})

    def _build_snapshot(self, muestra, request_user):
        lote = muestra.lote
        interpretation = _interpretation_from_sample(muestra)
        tests = [item for item in _sample_tests_for_lote(lote) if item["muestra"] == muestra.id] if lote else []
        equipo = getattr(muestra, "referencia_equipo", None)
        empresa = getattr(lote, "cliente_empresa", None) if lote else None

        comments = {
            "predefinidos": (
                interpretation.get("selected_predefined_comments")
                or interpretation.get("comentarios_predefinidos")
                or interpretation.get("predefined_comments")
                or []
            ),
            "manuales": interpretation.get("comentarios_manuales") or [],
            "conclusion": interpretation.get("conclusion") or interpretation.get("comentario_proveedor") or "",
        }

        return {
            "generated_at": timezone.now().isoformat(),
            "generated_by": {
                "id": getattr(request_user, "id", None),
                "name": _user_name(request_user),
                "email": getattr(request_user, "email", None),
            },
            "empresa": {
                "id": getattr(empresa, "id", None),
                "nombre": getattr(empresa, "nombre", None) or getattr(lote, "cliente_ocasional_nombre", None),
                "nit": getattr(empresa, "nit", None),
                "direccion": getattr(empresa, "direccion", None),
                "telefono": getattr(empresa, "telefono", None),
                "email": getattr(empresa, "email", None),
                "contacto_email": getattr(lote, "contacto_email", None),
            },
            "lote": {
                "id": getattr(lote, "id", None),
                "tipo_gestion": getattr(getattr(lote, "tipo_gestion", None), "nombre", None),
                "fecha_recepcion": str(getattr(lote, "fecha_recepcion", "") or ""),
                "fecha_envio_muestras": str(getattr(lote, "fecha_envio", "") or ""),
                "contacto_email": getattr(lote, "contacto_email", None),
                "contacto_nombre": getattr(lote, "contacto_nombre", None),
            },
            "muestra": {
                "id": muestra.id,
                "fecha_toma": muestra.fecha_toma.isoformat() if muestra.fecha_toma else None,
                "tipo_muestra": muestra.tipo_muestra,
                "condicion": muestra.condicion,
                "referencia_marca": muestra.referencia_marca,
                "contacto_cliente": muestra.contacto_cliente,
                "equipo_placa": muestra.equipo_placa,
                "periodo_servicio_aceite": muestra.periodo_servicio_aceite,
                "unidad_periodo_aceite": muestra.unidad_periodo_aceite,
                "periodo_servicio_equipo": muestra.periodo_servicio_equipo,
                "unidad_periodo_equipo": muestra.unidad_periodo_equipo,
            },
            "equipo": {
                "id": getattr(equipo, "id", None),
                "nombre": getattr(equipo, "nombre", None) or getattr(equipo, "name", None) or muestra.equipo_placa,
                "codigo": getattr(equipo, "codigo_equipo", None) or getattr(equipo, "codigo", None),
            },
            "resultados": tests,
            "comentarios": comments,
            "graficas": {
                "activas": interpretation.get("graficas_activas", True),
                "seleccionadas": interpretation.get("graficas_seleccionadas") or [],
            },
            "interpretacion": interpretation,
        }

    def _next_version(self, muestra_id):
        last = (
            Reporte.objects
            .filter(muestra_id=muestra_id)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        )
        return (last or 0) + 1

    def _create_from_interpretation(self, muestra, request):
        version = self._next_version(muestra.id)
        snapshot = self._build_snapshot(muestra, request.user)
        snapshot["version"] = version
        snapshot = _json_safe(snapshot)
        comments = snapshot.get("comentarios", {})

        firma_ruta = request.data.get("firma_ruta") or request.data.get("firma")
        firma_base64 = request.data.get("firma_base64")
        if not firma_ruta and firma_base64:
            firma_ruta = _save_signature_base64(firma_base64)
        if not firma_ruta:
            firma_ruta = _default_signature_path(request.user)
        responsable = request.data.get("responsable") or _user_name(request.user)

        return Reporte.objects.create(
            muestra=muestra,
            lote=muestra.lote,
            version=version,
            snapshot=snapshot,
            fecha_emision=timezone.now(),
            fecha_generacion=timezone.now(),
            usuario_emision=request.user,
            comentarios="\n".join((comments.get("predefinidos") or []) + (comments.get("manuales") or [])),
            conclusiones=comments.get("conclusion", ""),
            firma_ruta=firma_ruta,
            Responsable=responsable,
            estatus="generado",
            visible_cliente=False,
        )

    @action(detail=False, methods=["post"], url_path="generate-from-interpretation")
    def generate_from_interpretation(self, request):
        muestra_id = request.data.get("muestra") or request.data.get("muestra_id")
        if not muestra_id:
            return Response({"detail": "Debe enviar la muestra."}, status=status.HTTP_400_BAD_REQUEST)

        muestra = (
            Muestra.objects
            .select_related("lote", "lote__cliente_empresa", "lote__tipo_gestion", "referencia_equipo")
            .filter(pk=muestra_id)
            .first()
        )
        if not muestra:
            return Response({"detail": "Muestra no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if muestra.estado_operativo != "activa":
            return Response({"detail": "No puede generar un reporte para una muestra invalidada."}, status=status.HTTP_409_CONFLICT)
        if not muestra.is_revisado:
            return Response({"detail": "No puede generar reporte: la muestra aun no esta revisada."}, status=status.HTTP_400_BAD_REQUEST)
        if not _has_interpretation(muestra):
            return Response({"detail": "No puede generar reporte: primero guarde la interpretacion de la muestra."}, status=status.HTTP_400_BAD_REQUEST)

        reporte = self._create_from_interpretation(muestra, request)
        _mark_lote_reported_if_ready(muestra.lote)
        return Response(ReporteSerializer(reporte, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="generate-batch-from-interpretation")
    def generate_batch_from_interpretation(self, request):
        lote_id = request.data.get("lote") or request.data.get("lote_id")
        if not lote_id:
            return Response({"detail": "Debe enviar el lote."}, status=status.HTTP_400_BAD_REQUEST)
        lote = LoteMuestras.objects.filter(pk=lote_id).first()
        if not lote:
            return Response({"detail": "Lote no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        samples = list(
            Muestra.objects
            .select_related("lote", "lote__cliente_empresa", "lote__tipo_gestion", "referencia_equipo")
            .filter(lote=lote, estado_operativo="activa")
            .order_by("id")
        )
        not_reviewed = [sample.id for sample in samples if not sample.is_revisado]
        without_interpretation = [sample.id for sample in samples if not _has_interpretation(sample)]
        if not_reviewed or without_interpretation:
            return Response({
                "detail": "No se puede generar el lote completo hasta que todas las muestras estén revisadas y tengan contenido de interpretación guardado.",
                "muestras_sin_revision": not_reviewed,
                "muestras_sin_interpretacion": without_interpretation,
            }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            reports = [self._create_from_interpretation(sample, request) for sample in samples]
            _mark_lote_reported_if_ready(lote)
        return Response({
            "detail": f"Se generaron {len(reports)} reportes individuales para el lote {lote.id}.",
            "generated": len(reports),
            "reports": [
                {"id": report.id, "muestra": report.muestra_id, "consecutivo": report.consecutivo, "version": report.version}
                for report in reports
            ],
        }, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=["get"], url_path="preview-from-interpretation")
    def preview_from_interpretation(self, request):
        muestra_id = request.query_params.get("muestra") or request.query_params.get("muestra_id")
        if not muestra_id:
            return Response({"detail": "Debe enviar la muestra."}, status=status.HTTP_400_BAD_REQUEST)

        muestra = (
            Muestra.objects
            .select_related("lote", "lote__cliente_empresa", "lote__tipo_gestion", "referencia_equipo")
            .filter(pk=muestra_id)
            .first()
        )
        if not muestra:
            return Response({"detail": "Muestra no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        snapshot = self._build_snapshot(muestra, request.user)
        temp = Reporte(
            muestra=muestra,
            lote=muestra.lote,
            version=self._next_version(muestra.id),
            snapshot=snapshot,
            fecha_emision=timezone.now(),
            fecha_generacion=timezone.now(),
            usuario_emision=request.user,
            consecutivo="VISTA-PREVIA",
            Responsable=_user_name(request.user),
            firma_ruta=_default_signature_path(request.user),
        )
        html_content = self._render_report_html(temp)
        pdf_result = self._generar_pdf(html_content)
        if pdf_result.get("error"):
            return Response({"error": True, "message": pdf_result["error"]}, status=500)

        response = HttpResponse(pdf_result["pdf"], content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="vista_previa_reporte.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response

    @action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        queryset = self.get_queryset()
        # This endpoint is a read model for the library, not a report-detail
        # endpoint. Avoid loading delivery rows and large JSON snapshots.
        reportes = ReporteSummarySerializer(
            queryset.prefetch_related(None).defer(
                "snapshot",
                "comentarios",
                "conclusiones",
                "notas_internas",
                "firma_ruta",
            )[:300],
            many=True,
            context=self.get_serializer_context(),
        ).data
        summary = queryset.aggregate(
            total=Count("pk", distinct=True),
            enviados=Count(
                "pk",
                filter=Q(estatus="enviado") | Q(fecha_envio__isnull=False),
                distinct=True,
            ),
            pendientes_envio=Count(
                "pk",
                filter=Q(fecha_envio__isnull=True) & ~Q(estatus="enviado"),
                distinct=True,
            ),
            visibles_cliente=Count(
                "pk", filter=Q(visible_cliente=True), distinct=True
            ),
        )

        return Response({
            "summary": summary,
            # La interfaz agrupa por lote; no construimos bloques por empresa ni
            # recorremos nuevamente todo el queryset para producirlos.
            "groups": [],
            "results": reportes,
        })

    @action(detail=True, methods=["post"], url_path="publish-client")
    def publish_client(self, request, pk=None):
        reporte = self.get_object()
        if not reporte.fecha_aprobacion or not reporte.usuario_aprobacion_id:
            return Response(
                {"detail": "El reporte debe estar aprobado antes de publicarlo al cliente."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reporte.visible_cliente = True
        reporte.save(update_fields=["visible_cliente"])
        ReporteEnvio.objects.create(reporte=reporte, canal="app", enviado_por=request.user, estado="enviado")
        return Response(ReporteSerializer(reporte, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="unpublish-client")
    def unpublish_client(self, request, pk=None):
        reporte = self.get_object()
        reporte.visible_cliente = False
        reporte.save(update_fields=["visible_cliente"])
        return Response(ReporteSerializer(reporte, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="send-email")
    def send_email_report(self, request, pk=None):
        reporte = self.get_object()
        if not reporte.fecha_aprobacion or not reporte.usuario_aprobacion_id:
            return Response(
                {"detail": "El reporte debe estar aprobado antes de enviarlo al cliente."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # No se pide correo manual en frontend. El backend usa el correo asociado al lote/muestra.
        # Aun así se acepta override opcional para pruebas internas o reenvíos especiales.
        recipients = request.data.get("recipients") or request.data.get("destinatarios") or []
        if isinstance(recipients, str):
            recipients = [item.strip() for item in recipients.split(",") if item.strip()]
        if not recipients:
            recipients = _report_recipient_emails(reporte)

        if not recipients:
            return Response(
                {"detail": "No hay contacto_email asociado al lote/muestra ni correo de empresa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject = f"Reporte {reporte.consecutivo} - muestra {reporte.muestra_id}"
        message = request.data.get("message") or (
            f"Se ha generado el reporte {reporte.consecutivo} versión {reporte.version} "
            f"para la muestra {reporte.muestra_id}. Puede consultarlo en la plataforma."
        )

        download_url = request.build_absolute_uri(
            f"/api/lubrication/reports/imprimir_reporte/?pdf={reporte.id}"
        )
        message = f"{message}\n\nDescargar reporte: {download_url}"

        estado = "enviado"
        error = None
        try:
            pdf_result = self._generar_pdf(self._render_report_html(reporte))
            if pdf_result.get("error"):
                raise RuntimeError(pdf_result["error"])

            email = EmailMessage(
                subject,
                message,
                getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipients,
            )
            email.attach(
                f"{reporte.consecutivo}_v{reporte.version}.pdf",
                pdf_result["pdf"],
                "application/pdf",
            )
            email.send(fail_silently=False)
        except Exception as exc:
            estado = "fallido"
            error = str(exc)

        reporte.fecha_envio = timezone.now()
        reporte.usuario_envio = request.user
        if estado == "enviado":
            reporte.estatus = "enviado"
            reporte.visible_cliente = True
        reporte.save(update_fields=["fecha_envio", "usuario_envio", "estatus", "visible_cliente"])

        for email in recipients:
            ReporteEnvio.objects.create(
                reporte=reporte,
                canal="email",
                destinatario_email=email,
                enviado_por=request.user,
                estado=estado,
                error=error,
            )

        if estado == "fallido":
            return Response({"detail": "No se pudo enviar el correo.", "error": error}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "detail": "Reporte enviado.",
            "recipients": recipients,
            "reporte": ReporteSerializer(reporte, context=self.get_serializer_context()).data,
        })

    def _approved_reports_for_batch(self, lote_id):
        lote = LoteMuestras.objects.filter(pk=lote_id).prefetch_related("muestras").first()
        if not lote:
            return None, [], []

        accessible = self.get_queryset().filter(lote_id=lote_id)
        if not accessible.exists() and not (self.request.user.is_superuser or self.request.user.role == User.Role.GLOBAL):
            return None, [], []

        reports = []
        missing = []
        for muestra in lote.muestras.all().order_by("id"):
            reporte = (
                accessible
                .filter(
                    muestra_id=muestra.id,
                    fecha_aprobacion__isnull=False,
                    usuario_aprobacion__isnull=False,
                )
                .exclude(estatus="anulado")
                .order_by("-version", "-id")
                .first()
            )
            if reporte:
                reports.append(reporte)
            else:
                missing.append(muestra.id)
        return lote, reports, missing

    def _batch_reports_or_response(self, lote_id):
        lote, reports, missing = self._approved_reports_for_batch(lote_id)
        if not lote:
            return None, None, Response({"detail": "Lote no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if missing:
            return None, None, Response(
                {
                    "detail": "El lote solo puede exportarse o enviarse cuando todas sus muestras tienen un reporte aprobado.",
                    "muestras_sin_reporte_aprobado": missing,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not reports:
            return None, None, Response({"detail": "El lote no tiene reportes aprobados."}, status=status.HTTP_400_BAD_REQUEST)
        return lote, reports, None

    def _pdf_bytes_for_report(self, reporte):
        result = self._generar_pdf(self._render_report_html(reporte))
        if result.get("error"):
            raise RuntimeError(result["error"])
        return result["pdf"]

    def _batch_file(self, lote, reports, file_format):
        rendered = [(report, self._pdf_bytes_for_report(report)) for report in reports]
        if file_format == "zip":
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for report, pdf in rendered:
                    archive.writestr(
                        f"{report.muestra_id}_{report.consecutivo}_v{report.version}.pdf",
                        pdf,
                    )
            return output.getvalue(), f"reportes_{lote.id}.zip", "application/zip"

        writer = PdfWriter()
        for _, pdf in rendered:
            reader = PdfReader(io.BytesIO(pdf))
            for page in reader.pages:
                writer.add_page(page)
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue(), f"reportes_{lote.id}.pdf", "application/pdf"

    @action(detail=False, methods=["get"], url_path="batch-export")
    def export_batch(self, request):
        lote_id = request.query_params.get("lote")
        file_format = str(request.query_params.get("formato") or "pdf").lower()
        if not lote_id:
            return Response({"detail": "El parámetro lote es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
        if file_format not in ["pdf", "zip"]:
            return Response({"detail": "El formato debe ser pdf o zip."}, status=status.HTTP_400_BAD_REQUEST)

        lote, reports, error_response = self._batch_reports_or_response(lote_id)
        if error_response:
            return error_response
        try:
            content, filename, content_type = self._batch_file(lote, reports, file_format)
        except Exception as exc:
            logger.exception("No se pudo generar el archivo consolidado del lote")
            return Response({"detail": "No se pudo generar el archivo del lote.", "error": str(exc)}, status=500)

        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "private, no-store"
        return response

    @action(detail=False, methods=["post"], url_path="batch-send")
    def send_batch_email(self, request):
        lote_id = request.data.get("lote")
        file_format = str(request.data.get("formato") or "pdf").lower()
        if not lote_id:
            return Response({"detail": "El lote es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
        if file_format not in ["pdf", "zip"]:
            return Response({"detail": "El formato debe ser pdf o zip."}, status=status.HTTP_400_BAD_REQUEST)

        lote, reports, error_response = self._batch_reports_or_response(lote_id)
        if error_response:
            return error_response
        recipients = request.data.get("recipients") or request.data.get("destinatarios") or []
        if isinstance(recipients, str):
            recipients = [item.strip() for item in recipients.split(",") if item.strip()]
        if not recipients:
            recipients = _report_recipient_emails(reports[0])
        if not recipients:
            return Response({"detail": "El lote no tiene un correo de contacto asociado."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            content, filename, content_type = self._batch_file(lote, reports, file_format)
            email = EmailMessage(
                f"Reportes aprobados del lote {lote.id}",
                request.data.get("message") or f"Se adjuntan los reportes aprobados de las {len(reports)} muestras del lote {lote.id}.",
                getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipients,
            )
            email.attach(filename, content, content_type)
            email.send(fail_silently=False)
        except Exception as exc:
            logger.exception("No se pudo enviar el lote de reportes")
            for report in reports:
                for recipient in recipients:
                    ReporteEnvio.objects.create(
                        reporte=report, canal="email", destinatario_email=recipient,
                        enviado_por=request.user, estado="fallido", error=str(exc),
                    )
            return Response({"detail": "No se pudo enviar el lote.", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        now = timezone.now()
        for report in reports:
            report.fecha_envio = now
            report.usuario_envio = request.user
            report.estatus = "enviado"
            report.visible_cliente = True
            report.save(update_fields=["fecha_envio", "usuario_envio", "estatus", "visible_cliente"])
            for recipient in recipients:
                ReporteEnvio.objects.create(
                    reporte=report, canal="email", destinatario_email=recipient,
                    enviado_por=request.user, estado="enviado",
                )
        return Response({
            "detail": "Lote de reportes enviado.",
            "lote": lote.id,
            "formato": file_format,
            "muestras": [report.muestra_id for report in reports],
            "recipients": recipients,
        })

    @action(detail=True, methods=["get"], url_path="versions")
    def versions(self, request, pk=None):
        reporte = self.get_object()
        versions = (
            Reporte.objects
            .filter(muestra_id=reporte.muestra_id)
            .select_related("muestra", "lote", "lote__cliente_empresa", "usuario_emision", "usuario_envio")
            .order_by("-version")
        )
        return Response(ReporteSerializer(versions, many=True, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        reporte = self.get_object()
        reporte.usuario_aprobacion = request.user
        reporte.fecha_aprobacion = timezone.now()
        reporte.estatus = "aprobado"
        reporte.save(update_fields=["usuario_aprobacion", "fecha_aprobacion", "estatus"])
        return Response(ReporteSerializer(reporte, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def enviar_aprobacion(self, request, pk=None):
        reporte = self.get_object()
        reporte.estatus = "pendiente_aprobacion"
        reporte.save(update_fields=["estatus"])
        return Response(ReporteSerializer(reporte, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"])
    def firma_base64(self, request, pk=None):
        reporte = self.get_object()
        if not reporte.firma_ruta:
            return Response({"error": "No hay firma disponible"}, status=404)
        try:
            file_path = reporte.firma_ruta.replace("/media/", "") if reporte.firma_ruta.startswith("/media/") else reporte.firma_ruta
            if not default_storage.exists(file_path):
                return Response({"error": "Archivo de firma no encontrado"}, status=404)
            with default_storage.open(file_path, "rb") as file:
                encoded = base64.b64encode(file.read()).decode("utf-8")
                mime = "image/jpeg" if file_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
                return Response({
                    "firma_base64": f"data:{mime};base64,{encoded}",
                    "mime_type": mime,
                    "file_name": os.path.basename(file_path),
                })
        except Exception as exc:
            logger.exception("Error leyendo firma")
            return Response({"error": str(exc)}, status=500)

    @action(detail=False, methods=["post"], url_path="upload-signature")
    def upload_signature(self, request):
        if "file" not in request.FILES:
            return Response({"error": "No se encontro ningun archivo en la solicitud"}, status=status.HTTP_400_BAD_REQUEST)
        file = request.FILES["file"]
        if not file.content_type.startswith("image/"):
            return Response({"error": "El archivo debe ser una imagen"}, status=status.HTTP_400_BAD_REQUEST)
        if file.size > 2 * 1024 * 1024:
            return Response({"error": "El archivo no puede ser mayor a 2MB"}, status=status.HTTP_400_BAD_REQUEST)

        filename = f"firma_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{os.path.splitext(file.name)[1]}"
        saved_path = default_storage.save(os.path.join(request.POST.get("folder", "firmas"), filename), file)
        file_url = getattr(settings, "MEDIA_URL", "/media/") + saved_path
        return Response({"message": "Firma guardada exitosamente", "filePath": file_url, "fileName": filename, "savedPath": saved_path}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def imprimir_reporte(self, request):
        reporte_id = request.query_params.get("pdf")
        if not reporte_id:
            return Response({"error": True, "message": 'Parametro "pdf" requerido'}, status=400)

        if str(reporte_id).startswith("M"):
            reporte = self.get_queryset().filter(muestra_id=reporte_id).order_by("-version").first()
        else:
            try:
                reporte = self.get_queryset().filter(id=int(reporte_id)).first()
            except ValueError:
                reporte = self.get_queryset().filter(consecutivo=reporte_id).first()

        if not reporte:
            return Response({"error": True, "message": "Reporte no encontrado"}, status=404)

        html_content = self._render_report_html(reporte)
        pdf_result = self._generar_pdf(html_content)
        if pdf_result.get("error"):
            return Response({"error": True, "message": pdf_result["error"]}, status=500)

        response = HttpResponse(pdf_result["pdf"], content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="reporte_{reporte.consecutivo}_v{reporte.version}.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response

    def _render_report_html(self, reporte):
        snapshot = reporte.snapshot or {}
        context = self._snapshot_to_template_context(reporte, snapshot)

        template_paths = [
            os.path.join(settings.BASE_DIR, "apps", "media", "templates", "globalreport.html"),
            os.path.join(settings.BASE_DIR, "templates", "globalreport.html"),
            "globalreport.html",
        ]
        for template_path in template_paths:
            try:
                template = get_template(template_path)
                return template.render(context)
            except Exception:
                continue

        fallback = Template("""
        <html>
          <head>
            <style>
              body { font-family: Arial, sans-serif; font-size: 11px; }
              table { width: 100%; border-collapse: collapse; }
              th, td { border: 1px solid #111; padding: 5px; }
              th { background: #eee; }
              h1, h2 { text-align: center; }
            </style>
          </head>
          <body>
            <h1>ORDEN DE ANALISIS</h1>
            <h2>{{ consecutivo }} - Version {{ version }}</h2>
            <p><b>Cliente:</b> {{ empresa }}</p>
            <p><b>Muestra:</b> {{ muestra.id }}</p>
            <table>
              <thead><tr><th>Analisis</th><th>Metodo</th><th>Resultado</th><th>Unidades</th><th>Limite</th><th>Comentario</th></tr></thead>
              <tbody>
              {% for p in pruebas_estructuradas %}
                <tr>
                  <td>{{ p.prueba.nombre }}</td>
                  <td>{{ p.prueba.metodo_referencia }}</td>
                  <td>{{ p.valor }}</td>
                  <td>{{ p.unidad }}</td>
                  <td>{{ p.limite }}</td>
                  <td>{{ p.estatus }}</td>
                </tr>
              {% endfor %}
              </tbody>
            </table>
            <h3>COMENTARIOS</h3>
            <ol>{% for c in comentarios_lista %}<li>{{ c }}</li>{% endfor %}</ol>
            <h3>CONCLUSIONES</h3>
            <p>{{ conclusiones }}</p>
          </body>
        </html>
        """)
        return fallback.render(Context(context))

    def _result_structure_rows(self, item, nombre, metodo, unidad, parent_limit, parent_estado):
        evaluation = item.get("evaluacion_limite") or {}
        details = item.get("limite_detalles") or evaluation.get("details") or []
        result_outcomes = (
            evaluation.get("result_outcomes")
            or (evaluation.get("raw") or {}).get("result_outcomes")
            or []
        )
        fallback_row = {
            "id": item.get("id"),
            "analisis": nombre,
            "subanalisis": "",
            "metodo": metodo,
            "resultado": item.get("resultado_resumen") or "-",
            "unidad": unidad,
            "limite": parent_limit,
            "comentario": parent_estado,
            "comentario_class": _report_comment_class(parent_estado),
            "comentario_detalle": "",
            "campos": [],
        }
        if not details:
            return [fallback_row]

        result_configuration = item.get("configuracion_resultados") or {}
        authored_results = (item.get("prueba") or {}).get("resultados") or []

        def normalized(value):
            return str(value or "").strip().casefold()

        def authored_result_for(group):
            result_id = group.get("result_id")
            label = normalized(group.get("label"))
            for configured_result in authored_results:
                if result_id and str(configured_result.get("id")) == str(result_id):
                    return configured_result
                if label and label in {
                    normalized(configured_result.get("nombre")),
                    normalized(configured_result.get("acronimo")),
                }:
                    return configured_result
            return None

        def result_unit(result_id, result_label):
            candidates = []
            for key, config in result_configuration.items():
                if not isinstance(config, dict):
                    continue
                configured_id = config.get("resultado_id")
                configured_label = str(config.get("resultado") or "").strip().casefold()
                if result_id and str(configured_id or key) == str(result_id):
                    candidates.append(config.get("unidad"))
                elif result_label and configured_label == str(result_label).strip().casefold():
                    candidates.append(config.get("unidad"))
            return next((value for value in candidates if value not in [None, ""]), "")

        def clean_group_label(label, index):
            text = str(label or "").strip()
            replacements = {
                "Secuencia 1": "Secuencia I",
                "Secuencia 2": "Secuencia II",
                "Secuencia 3": "Secuencia III",
                "secuencia 1": "Secuencia I",
                "secuencia 2": "Secuencia II",
                "secuencia 3": "Secuencia III",
            }
            for old, new in replacements.items():
                text = text.replace(old, new)
            return text or "Resultado"

        groups = []
        group_map = {}
        for index, detail in enumerate(details):
            key = detail.get("result_id") or detail.get("result_label") or detail.get("division_label") or "__default__"
            if key not in group_map:
                group_map[key] = {
                    "key": key,
                    "result_id": detail.get("result_id"),
                    "label": detail.get("result_label") or detail.get("division_label") or "Resultado",
                    "fields": [],
                }
                groups.append(group_map[key])
            field_status = _report_status(detail.get("estado") or detail.get("status"), detail.get("passed"))
            field_label = _clean_limit_label(
                detail.get("field_label") or detail.get("field") or detail.get("componente") or "Resultado"
            )
            value = (
                detail.get("resultado_valor_label")
                if detail.get("resultado_valor_label") not in [None, ""]
                else detail.get("value_label")
            )
            if value in [None, ""]:
                value = detail.get("resultado_valor") if detail.get("resultado_valor") not in [None, ""] else detail.get("value")
            field_unit = (
                result_unit(detail.get("result_id"), detail.get("result_label") or detail.get("division_label"))
                or detail.get("unit")
                or unidad
            )
            group_map[key]["fields"].append({
                "component_id": detail.get("component_id") or detail.get("componente_id"),
                "label": field_label,
                "resultado": value if value not in [None, ""] else "-",
                "unidad": field_unit if field_unit not in [None, ""] else "-",
                "status": field_status,
                "status_class": _report_comment_class(field_status),
                "reason": detail.get("reason") or "",
                **_report_limit_bands(detail),
            })

        rows = []
        for index, group in enumerate(groups):
            fields = group["fields"]
            authored_result = authored_result_for(group)
            authored_components = []
            if authored_result:
                for division in authored_result.get("divisiones") or []:
                    authored_components.extend(division.get("componentes") or [])

            component_order = {
                str(component.get("id")): position
                for position, component in enumerate(authored_components)
                if component.get("id") is not None
            }
            label_order = {
                normalized(component.get("acronimo") or component.get("nombre")): position
                for position, component in enumerate(authored_components)
            }
            fields.sort(key=lambda field: (
                component_order.get(str(field.get("component_id")), 10000),
                label_order.get(normalized(field.get("label")), 10000),
            ))

            field_by_component = {
                str(field.get("component_id")): field
                for field in fields
                if field.get("component_id") is not None
            }
            field_by_label = {normalized(field.get("label")): field for field in fields}
            display_tokens = []
            if authored_result:
                for division_index, division in enumerate(authored_result.get("divisiones") or []):
                    if division_index:
                        display_tokens.append({"type": "break", "value": ""})
                    disposition = division.get("disposicion") or []
                    if not disposition:
                        for component_index, component in enumerate(division.get("componentes") or []):
                            if component_index:
                                display_tokens.append({"type": "separator", "value": " / "})
                            disposition.append({
                                "tipo": "componente",
                                "componente_id": component.get("id"),
                                "valor": component.get("acronimo") or component.get("nombre"),
                            })
                    for token in disposition:
                        if token.get("tipo") == "separador":
                            display_tokens.append({"type": "separator", "value": token.get("valor") or " / "})
                            continue
                        field = field_by_component.get(str(token.get("componente_id")))
                        if not field:
                            field = field_by_label.get(normalized(token.get("valor")))
                        if field:
                            display_tokens.append({"type": "field", "field": field})
            if not display_tokens:
                for field_index, field in enumerate(fields):
                    if field_index:
                        display_tokens.append({"type": "separator", "value": " / "})
                    display_tokens.append({"type": "field", "field": field})

            states = [field["status"] for field in fields]
            hierarchy_outcome = next((
                outcome for outcome in result_outcomes
                if (
                    group.get("result_id")
                    and str(outcome.get("result_id")) == str(group.get("result_id"))
                ) or (
                    str(outcome.get("label") or "").strip().casefold()
                    == str(group.get("label") or "").strip().casefold()
                )
            ), None)
            hierarchy_status = _report_status(
                (hierarchy_outcome or {}).get("estado"),
                (hierarchy_outcome or {}).get("passed"),
            ) if hierarchy_outcome else None
            if hierarchy_status:
                estado = hierarchy_status
            elif "CRÍTICO" in states:
                estado = "CRÍTICO"
            elif "ALERTA" in states:
                estado = "ALERTA"
            elif "ACEPTABLE" in states:
                estado = "ACEPTABLE"
            elif "INFORMATIVO" in states:
                estado = "INFORMATIVO"
            else:
                estado = parent_estado

            group_label = clean_group_label(group.get("label"), index)
            subanalysis = group_label if len(groups) > 1 or group_label.strip().lower() != str(nombre).strip().lower() else ""
            dominant = [field["label"] for field in fields if field["status"] == estado]
            result_parts = [
                f"{field['label']}: {field['resultado']}" if len(fields) > 1 else str(field["resultado"])
                for field in fields
            ]
            rows.append({
                "id": f"{item.get('id')}-{index}",
                "analisis": nombre,
                "subanalisis": subanalysis,
                "metodo": metodo,
                "resultado": " / ".join(result_parts) if result_parts else "-",
                "unidad": (
                    (authored_result or {}).get("unidad_medida")
                    or (fields[0]["unidad"] if fields else unidad)
                ),
                "limite": " / ".join(field["acceptable"] for field in fields) if fields else parent_limit,
                "limite_aceptable": " | ".join(
                    f"{field['label']}: {field['acceptable']}" if len(fields) > 1 else field["acceptable"]
                    for field in fields if field.get("acceptable")
                ),
                "limite_alerta": " | ".join(
                    f"{field['label']}: {field['warning']}" if len(fields) > 1 else field["warning"]
                    for field in fields if field.get("warning")
                ),
                "limite_critico": " | ".join(
                    f"{field['label']}: {field['critical']}" if len(fields) > 1 else field["critical"]
                    for field in fields if field.get("critical")
                ),
                "comentario": estado,
                "comentario_class": _report_comment_class(estado),
                "comentario_detalle": ", ".join(dominant),
                "campos": fields,
                "display_tokens": display_tokens,
            })
        return rows

    def _snapshot_to_template_context(self, reporte, snapshot):
        muestra = snapshot.get("muestra", {})
        empresa = snapshot.get("empresa", {})
        equipo = snapshot.get("equipo", {})
        comentarios = snapshot.get("comentarios", {})
        resultados = snapshot.get("resultados", [])

        pruebas = []
        for item in resultados:
            prueba = item.get("prueba", {})
            nombre = prueba.get("nombre_variable") or prueba.get("acronimo") or "-"
            metodo = item.get("metodo_codigo") or item.get("metodo") or "-"
            unidad = item.get("unidad") or prueba.get("unidad_medida") or "-"
            limite = _clean_limit_label(item.get("limite_resumen") or (item.get("evaluacion_limite") or {}).get("summary") or "-")
            estado = self._estado_reporte(item.get("estado_limite"))

            pruebas.extend(self._result_structure_rows(item, nombre, metodo, unidad, limite, estado))

        comments = (comentarios.get("predefinidos") or []) + (comentarios.get("manuales") or [])
        conclusion = comentarios.get("conclusion") or reporte.conclusiones or ""

        firma_url = getattr(reporte, "firma_ruta", None) or ""
        firma_src = ""
        if firma_url:
            firma_path = firma_url
            if firma_path.startswith(getattr(settings, "MEDIA_URL", "/media/")):
                firma_path = firma_path.replace(getattr(settings, "MEDIA_URL", "/media/"), "", 1)
            if firma_path.startswith("/media/"):
                firma_path = firma_path.replace("/media/", "", 1)
            if firma_path.startswith("/"):
                firma_path = firma_path.lstrip("/")
            try:
                if default_storage.exists(firma_path):
                    with default_storage.open(firma_path, "rb") as fh:
                        raw = fh.read()
                    ext = os.path.splitext(firma_path)[1].lower()
                    mime = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
                    firma_src = f"data:{mime};base64,{base64.b64encode(raw).decode('utf-8')}"
                else:
                    firma_src = firma_url
            except Exception:
                firma_src = firma_url

        logo_global = "/media/templates/logo-globaloil.png"
        logo_report = "/media/templates/icon-report.png"

        return {
            "reporte_info": {
                "consecutivo": reporte.consecutivo,
                "version": reporte.version,
                "fecha_emision": reporte.fecha_emision.strftime("%d/%m/%Y") if reporte.fecha_emision else "N/A",
                "comentarios": "\n".join(comments),
                "conclusiones": conclusion,
                "responsable": getattr(reporte, "Responsable", None) or _user_name(reporte.usuario_emision) or "Responsable",
                "estatus": reporte.estatus,
                "with_limites": reporte.with_limites,
                "logo_global": logo_global,
                "logo_report": logo_report,
                "firma_url": firma_src,
            },
            "muestra_info": muestra,
            "equipo_info": equipo,
            "empresa_info": empresa,
            "lubricante_info": {"nombre_comercial": muestra.get("referencia_marca") or "N/A"},
            "pruebas_estructuradas": pruebas,
            "observaciones": "\n".join(comments) or "No hay comentarios registrados",
            "comentarios_lista": comments,
            "conclusiones": conclusion or "No hay conclusiones registradas",
            "responsable": getattr(reporte, "Responsable", None) or _user_name(reporte.usuario_emision) or "Responsable",
            "empresa": empresa.get("nombre") or "N/A",
            "consecutivo": reporte.consecutivo,
            "version": reporte.version,
            "fecha_emision": reporte.fecha_emision.strftime("%d/%m/%Y") if reporte.fecha_emision else "N/A",
            "muestra": muestra,
            "fecha_toma": _format_report_date(muestra.get("fecha_toma")),
        }

    def _estado_reporte(self, estado_limite):
        return _report_status(estado_limite)

    def _generar_pdf(self, html_content):
        try:
            pdf_file = io.BytesIO()

            def fetch_resources(uri, rel):
                if uri.startswith("http://") or uri.startswith("https://"):
                    return uri
                for base_path in [getattr(settings, "STATIC_ROOT", None), getattr(settings, "MEDIA_ROOT", None), settings.BASE_DIR]:
                    if base_path:
                        full_path = os.path.join(str(base_path), uri.lstrip("/"))
                        if os.path.exists(full_path):
                            return full_path
                return uri

            pisa_status = pisa.CreatePDF(html_content, dest=pdf_file, encoding="UTF-8", link_callback=fetch_resources)
            if pisa_status.err:
                return {"error": f"Error generando PDF: {pisa_status.err}"}
            content = pdf_file.getvalue()
            pdf_file.close()
            return {"pdf": content}
        except Exception as exc:
            logger.exception("Error generando PDF")
            return {"error": str(exc)}
