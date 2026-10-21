import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission
from apps.users.api.models.index import User
from apps.users.api.data_scope import accessible_company_ids

from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.serializers.muestras.index import (
    CreateMuestraSerializer,
    HistorialMuestraSerializer,
    MuestraListSerializer,
    MuestraSerializer,
)
from apps.muestras.services.operational_audit import record_operational_event
from apps.activesTree.api.models.index import AsignacionPuntoMuestreo, PuntoMuestreo

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
        company_ids = accessible_company_ids(user)
        if company_ids is None:
            return queryset
        return queryset.filter(
            Q(lote__cliente_empresa_id__in=company_ids) | Q(referencia_equipo__empresa_id__in=company_ids)
        ).distinct()

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception:
            logger.exception("Error en MuestraViewSetList")
            return Response(
                {"error": "Error interno del servidor"},
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
        "measurement_point": "muestras.editar",
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        company_ids = accessible_company_ids(user)
        if company_ids is None:
            return queryset
        return queryset.filter(
            Q(lote__cliente_empresa_id__in=company_ids) | Q(referencia_equipo__empresa_id__in=company_ids)
        ).distinct()

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
        # Invalidar una muestra también retira TODOS sus reportes publicados.
        # La operación es atómica: nunca puede quedar invalidada con informes visibles.
        from apps.reporte.api.models.index import Reporte
        with transaction.atomic():
            return self._invalidate_with_reports(request, muestra, reason)

    def _invalidate_with_reports(self, request, muestra, reason):
        muestra.estado_operativo = "invalidada"
        muestra.motivo_invalidacion = reason
        muestra.fecha_invalidacion = timezone.now()
        muestra.invalidada_por = request.user
        muestra.save(update_fields=["estado_operativo", "motivo_invalidacion", "fecha_invalidacion", "invalidada_por"])
        muestra.historial.create(usuario=request.user, accion="invalidacion", cambios={"motivo": reason}, estado_nuevo={"status": "invalidada"})
        record_operational_event(
            actor=request.user,
            action="muestra.invalidada",
            entity_type="muestra",
            entity_id=muestra.id,
            entity_label=muestra.id,
            muestra=muestra,
            detail="Muestra invalidada.",
            reason=reason,
            before={"estado_operativo": "activa"},
            after={"estado_operativo": "invalidada"},
        )
        from apps.reporte.api.models.index import Reporte
        for reporte in Reporte.objects.select_for_update().filter(muestra=muestra).exclude(estatus="anulado"):
            old_status, old_visible = reporte.estatus, reporte.visible_cliente
            reporte.estatus = "anulado"
            reporte.visible_cliente = False
            reporte.notas_internas = "\n".join(filter(None, [
                reporte.notas_internas, f"[Anulado por invalidación de muestra] {reason}",
            ]))
            reporte.save(update_fields=["estatus", "visible_cliente", "notas_internas"])
            record_operational_event(
                actor=request.user, action="reporte.anulado_por_muestra_invalidada",
                entity_type="reporte", entity_id=reporte.id,
                entity_label=f"{reporte.consecutivo} v{reporte.version}",
                lote=reporte.lote, muestra=muestra, reporte=reporte,
                detail="Reporte retirado por invalidación de muestra.", reason=reason,
                before={"estatus": old_status, "visible_cliente": old_visible},
                after={"estatus": "anulado", "visible_cliente": False},
            )
        if muestra.lote:
            muestra.lote.recalcular_estado(save=True)
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
        record_operational_event(
            actor=request.user,
            action="muestra.reactivada",
            entity_type="muestra",
            entity_id=muestra.id,
            entity_label=muestra.id,
            muestra=muestra,
            detail="Muestra reactivada.",
            reason=reason,
            before={"estado_operativo": "invalidada", "motivo_invalidacion": previous_reason},
            after={"estado_operativo": "activa"},
        )
        if muestra.lote:
            muestra.lote.recalcular_estado()
        return Response(MuestraSerializer(muestra, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["put"], url_path="measurement-point")
    @transaction.atomic
    def measurement_point(self, request, pk=None):
        """Set or clear the current sampling point without losing its history."""
        muestra = self.get_object()
        point_id = request.data.get("punto_muestreo_id")
        point = None
        if point_id not in (None, ""):
            point = PuntoMuestreo.objects.filter(pk=point_id, activo=True).select_related("maquina").first()
            if not point:
                return Response({"punto_muestreo_id": ["El punto de medida no existe o está inactivo."]}, status=status.HTTP_400_BAD_REQUEST)
            if not muestra.referencia_equipo_id:
                return Response({"punto_muestreo_id": ["Primero seleccione un equipo registrado para la muestra."]}, status=status.HTTP_400_BAD_REQUEST)
            if point.maquina_id != muestra.referencia_equipo_id:
                return Response({"punto_muestreo_id": ["El punto de medida no pertenece al equipo seleccionado."]}, status=status.HTTP_400_BAD_REQUEST)

        active = (
            AsignacionPuntoMuestreo.objects.select_for_update()
            .filter(muestra=muestra, activa=True)
            .select_related("punto_muestreo")
            .first()
        )
        if active and point and active.punto_muestreo_id == point.id:
            return Response(MuestraSerializer(muestra, context=self.get_serializer_context()).data)

        previous = (
            {"id": active.punto_muestreo_id, "nombre": active.punto_muestreo.nombre}
            if active else None
        )
        if active:
            active.close()
        if point:
            AsignacionPuntoMuestreo.objects.create(
                muestra=muestra,
                punto_muestreo=point,
                origen="manual",
                asignado_por=request.user,
            )

        current = {"id": point.id, "nombre": point.nombre} if point else None
        muestra.historial.create(
            usuario=request.user,
            accion="punto_muestreo",
            cambios={"punto_muestreo": {"anterior": previous, "nuevo": current}},
            estado_anterior={"punto_muestreo": previous},
            estado_nuevo={"punto_muestreo": current},
        )
        record_operational_event(
            actor=request.user,
            action="muestra.punto_muestreo_asignado" if point else "muestra.punto_muestreo_desasignado",
            entity_type="muestra",
            entity_id=muestra.id,
            entity_label=muestra.id,
            muestra=muestra,
            maquina=muestra.referencia_equipo,
            punto_muestreo=point,
            detail="Punto de medida actualizado para la muestra.",
            before={"punto_muestreo": previous},
            after={"punto_muestreo": current},
        )
        return Response(MuestraSerializer(muestra, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        muestra = self.get_object()
        history = muestra.historial.select_related("usuario").all()
        return Response(HistorialMuestraSerializer(history, many=True).data)
