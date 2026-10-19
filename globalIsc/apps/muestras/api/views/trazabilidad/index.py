from django.db.models import Count, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.muestras.api.models.auditoria import EventoAuditoriaOperativa
from apps.muestras.api.serializers.auditoria import EventoAuditoriaOperativaSerializer
from apps.users.api.models.index import User
from apps.utils.pagination import StandardResultsSetPagination
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission


CRITICAL_ACTIONS = (
    "resultado.corregido",
    "resultado.invalidado",
    "muestra.invalidada",
    "lote.cancelado",
    "lote.reabierto",
    "muestra.punto_muestreo_asignado",
    "limites.version_activada",
    "limites.matriz_importada",
)


class TrazabilidadViewSet(ActionPermissionMixin, viewsets.ReadOnlyModelViewSet):
    """Bitácora operacional paginada y filtrada en el servidor.

    La vista no sustituye los historiales especializados: los concentra para
    investigación administrativa y conserva el alcance de empresa del usuario.
    """

    serializer_class = EventoAuditoriaOperativaSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "trazabilidad.ver",
        "summary": "trazabilidad.ver",
        "filters": "trazabilidad.ver",
    }

    def _scoped_queryset(self):
        queryset = EventoAuditoriaOperativa.objects.select_related(
            "actor", "empresa", "lote", "muestra", "prueba_muestra",
            "reporte", "maquina", "punto_muestreo",
        )
        user = self.request.user
        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            queryset = queryset.filter(empresa_id=getattr(user, "empresa_id", None))
        return queryset

    @staticmethod
    def _option_rows(queryset, id_field, label_field):
        seen = set()
        rows = []
        for item in queryset.values(id_field, label_field).order_by(label_field).distinct():
            identifier = item.get(id_field)
            if identifier is None or identifier in seen:
                continue
            seen.add(identifier)
            rows.append({"id": str(identifier), "label": item.get(label_field) or str(identifier)})
        return rows

    def _filtered_queryset(self):
        queryset = self._scoped_queryset()
        params = self.request.query_params

        exact_filters = {
            "empresa": "empresa_id",
            "entidad": "tipo_entidad",
            "accion": "accion",
            "actor": "actor_id",
            "lote": "lote_id",
            "muestra": "muestra_id",
            "maquina": "maquina_id",
            "punto": "punto_muestreo_id",
            "prueba": "prueba_muestra_id",
            "reporte": "reporte_id",
            "origen": "origen",
        }
        for parameter, lookup in exact_filters.items():
            value = params.get(parameter)
            if value:
                queryset = queryset.filter(**{lookup: value})

        date_from = params.get("fecha_desde")
        date_to = params.get("fecha_hasta")
        if date_from:
            queryset = queryset.filter(creado_en__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(creado_en__date__lte=date_to)

        if params.get("criticos") in {"1", "true", "True"}:
            query = Q(accion__in=CRITICAL_ACTIONS)
            query |= Q(accion__icontains="correg") | Q(accion__icontains="invalid")
            query |= Q(accion__icontains="cancel") | Q(accion__icontains="reabr")
            queryset = queryset.filter(query)

        search = (params.get("buscar") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(entidad_etiqueta__icontains=search)
                | Q(detalle__icontains=search)
                | Q(motivo__icontains=search)
                | Q(accion__icontains=search)
                | Q(lote_id__icontains=search)
                | Q(muestra_id__icontains=search)
            )
        return queryset

    def get_queryset(self):
        return self._filtered_queryset()

    @action(detail=False, methods=["get"])
    def summary(self, request):
        queryset = self._filtered_queryset()
        critical_query = Q(accion__in=CRITICAL_ACTIONS) | Q(accion__icontains="correg") | Q(accion__icontains="invalid") | Q(accion__icontains="cancel") | Q(accion__icontains="reabr")
        return Response({
            "total": queryset.count(),
            "criticos": queryset.filter(critical_query).count(),
            "por_origen": list(queryset.values("origen").annotate(total=Count("id")).order_by("origen")),
            "por_accion": list(queryset.values("accion").annotate(total=Count("id")).order_by("-total", "accion")[:12]),
        })

    @action(detail=False, methods=["get"])
    def filters(self, request):
        """Opciones limitadas al alcance autorizado del usuario actual."""
        queryset = self._scoped_queryset()
        return Response({
            "empresas": self._option_rows(queryset, "empresa_id", "empresa__nombre"),
            "maquinas": self._option_rows(queryset, "maquina_id", "maquina__nombre"),
            "puntos": self._option_rows(queryset, "punto_muestreo_id", "punto_muestreo__nombre"),
            "lotes": self._option_rows(queryset, "lote_id", "lote_id"),
            "muestras": self._option_rows(queryset, "muestra_id", "muestra_id"),
            "responsables": self._option_rows(queryset, "actor_id", "actor__email"),
            "entidades": [
                {"id": item["tipo_entidad"], "label": item["tipo_entidad"].replace("_", " ").capitalize()}
                for item in queryset.values("tipo_entidad").order_by("tipo_entidad").distinct()
            ],
            "acciones": [
                {"id": item["accion"], "label": item["accion"].replace("_", " ").capitalize()}
                for item in queryset.values("accion").order_by("accion").distinct()
            ],
        })
