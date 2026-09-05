import logging

from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission
from apps.users.api.models.index import User

from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.serializers.muestras.index import (
    CreateMuestraSerializer,
    HistorialMuestraSerializer,
    MuestraListSerializer,
    MuestraSerializer,
)

logger = logging.getLogger(__name__)


def muestra_queryset():
    return Muestra.objects.select_related(
        "referencia_equipo",
        "referencia_equipo__empresa",
        "usuario_registro",
    ).prefetch_related(
        "atributos_tecnicos",
        "atributos_tecnicos__catalogo",
        "atributos_tecnicos__item",
        "referencia_equipo__empresa__user_set",
        "resultados",
        "resultados__prueba",
        "resultados__usuario_solicitud",
        "resultados__usuario_medicion",
        "resultados__usuario_revision",
    )


def muestra_list_queryset():
    resultados_queryset = PruebaMuestra.objects.select_related("prueba").only(
        "id",
        "muestra_id",
        "valor",
        "unidad",
        "estatus",
        "completada",
        "prueba__id",
        "prueba__nombre_variable",
        "prueba__acronimo",
        "prueba__unidad_medida",
        "prueba__condicion",
        "prueba__metodo",
    )

    return Muestra.objects.select_related(
        "referencia_equipo",
        "referencia_equipo__empresa",
    ).prefetch_related(
        "atributos_tecnicos",
        "atributos_tecnicos__catalogo",
        "atributos_tecnicos__item",
        Prefetch("resultados", queryset=resultados_queryset),
    )


class MuestraViewSetList(ActionPermissionMixin, viewsets.ModelViewSet):
    queryset = muestra_list_queryset()
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    default_read_permission = "muestras.ver"
    serializer_class = MuestraListSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role == User.Role.GLOBAL:
            return queryset
        return queryset.filter(referencia_equipo__empresa=user.empresa)

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.exception("Error en MuestraViewSetList")
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MuestraViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    queryset = muestra_queryset()
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "muestras.ver",
        "retrieve": "muestras.ver",
        "create": "muestras.crear",
        "update": "muestras.editar",
        "partial_update": "muestras.editar",
        "destroy": "muestras.eliminar",
        "history": "muestras.ver",
        "invalidate": "muestras.eliminar",
        "reactivate": "muestras.editar",
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role == User.Role.GLOBAL:
            return queryset
        return queryset.filter(referencia_equipo__empresa=user.empresa)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CreateMuestraSerializer
        return MuestraSerializer

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            logger.warning("Error al crear muestra: %s", str(e))
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        muestra = self.get_object()
        if muestra.is_ingresado or muestra.resultados.exists():
            return Response(
                {"detail": "La muestra ya entró al flujo y no puede eliminarse. Use Invalidar muestra para conservar el historial."},
                status=status.HTTP_409_CONFLICT,
            )
        if muestra.lote and muestra.lote.estado not in ["borrador", "registrado"]:
            return Response({"detail": "La muestra ya no puede retirarse de este lote."}, status=status.HTTP_409_CONFLICT)
        lote = muestra.lote
        response = super().destroy(request, *args, **kwargs)
        if lote:
            lote.recalcular_estado()
        return response

    @action(detail=True, methods=["post"], url_path="invalidate")
    def invalidate(self, request, pk=None):
        muestra = self.get_object()
        if muestra.estado_operativo == "invalidada":
            return Response({"detail": "La muestra ya está invalidada."}, status=status.HTTP_409_CONFLICT)
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return Response({"reason": ["Indique el motivo de invalidación."]}, status=status.HTTP_400_BAD_REQUEST)
        muestra.estado_operativo = "invalidada"
        muestra.motivo_invalidacion = reason
        muestra.fecha_invalidacion = timezone.now()
        muestra.invalidada_por = request.user
        muestra.save(update_fields=["estado_operativo", "motivo_invalidacion", "fecha_invalidacion", "invalidada_por"])
        muestra.historial.create(usuario=request.user, accion="invalidacion", cambios={"motivo": reason}, estado_nuevo={"status": "invalidada"})
        if muestra.lote:
            muestra.lote.recalcular_estado()
        return Response(MuestraSerializer(muestra, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        muestra = self.get_object()
        if muestra.estado_operativo != "invalidada":
            return Response({"detail": "La muestra no está invalidada."}, status=status.HTTP_409_CONFLICT)
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return Response({"reason": ["Indique el motivo de reactivación."]}, status=status.HTTP_400_BAD_REQUEST)
        previous_reason = muestra.motivo_invalidacion
        muestra.estado_operativo = "activa"
        muestra.motivo_invalidacion = ""
        muestra.fecha_invalidacion = None
        muestra.invalidada_por = None
        muestra.save(update_fields=["estado_operativo", "motivo_invalidacion", "fecha_invalidacion", "invalidada_por"])
        muestra.historial.create(
            usuario=request.user,
            accion="reactivacion",
            cambios={"motivo": reason, "invalidacion_anterior": previous_reason},
            estado_nuevo={"status": "activa"},
        )
        if muestra.lote:
            muestra.lote.recalcular_estado()
        return Response(MuestraSerializer(muestra, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        muestra = self.get_object()
        history = muestra.historial.select_related("usuario").all()
        return Response(HistorialMuestraSerializer(history, many=True).data)
