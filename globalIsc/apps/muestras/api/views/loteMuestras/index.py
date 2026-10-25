from django.db.models import Count, Q
from django.db.models import Prefetch
from rest_framework import filters, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.utils.pagination import StandardResultsSetPagination
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission
from apps.users.api.models.index import User
from apps.users.api.data_scope import scope_queryset
from apps.users.api.services import audit_user_action
from django.utils import timezone
from apps.muestras.api.models.auditoria import EventoAuditoriaOperativa
from apps.muestras.api.serializers.auditoria import EventoAuditoriaOperativaSerializer
from apps.muestras.services.operational_audit import record_operational_event

from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.serializers.loteMuestras.index import (
    LoteMuestrasListSerializer,
    LoteMuestrasDetailSerializer,
    LoteMuestrasCreateSerializer,
    LoteMuestraWorkspaceSerializer,
     AddMuestrasToLoteSerializer,
)


def _lot_snapshot(lote):
    return {
        "estado": lote.estado,
        "fecha_envio": lote.fecha_envio.isoformat() if lote.fecha_envio else None,
        "fecha_recepcion": lote.fecha_recepcion.isoformat() if lote.fecha_recepcion else None,
        "cliente_empresa": lote.cliente_empresa_id,
        "tipo_gestion": lote.tipo_gestion_id,
        "contacto_nombre": lote.contacto_nombre or "",
        "contacto_email": lote.contacto_email or "",
        "observaciones": lote.observaciones or "",
    }


class LoteMuestrasViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = [
        "id",
        "cliente_empresa__nombre",
        "tipo_gestion__nombre",
        "fecha_recepcion",
        "fecha_envio",
        "fecha_registro",
        "total_muestras_db",
        "estado",
    ]
    ordering = ["-fecha_recepcion", "-fecha_registro"]
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "lotes.ver",
        "retrieve": "lotes.ver",
        "resumen": "lotes.ver_resumen",
        "create": "lotes.crear",
        "update": "lotes.editar",
        "partial_update": "lotes.editar",
        "destroy": "lotes.eliminar",
        "recalcular_estado": "lotes.recalcular_estado",
        "timeline": "lotes.ver",
        "samples": "lotes.ver",
        "cancel": "lotes.eliminar",
        "reopen": "lotes.recalcular_estado",
        "register_draft": "lotes.editar",
    }

    def get_required_permission(self):
        # The same resource exposes the nested sample list (GET) and keeps the
        # established add-samples endpoint (POST). Their permissions differ.
        if getattr(self, "action", None) == "samples" and self.request.method != "GET":
            return "muestras.crear"
        return super().get_required_permission()

    @action(detail=True, methods=["post"], url_path="register")
    def register_draft(self, request, pk=None):
        lote = self.get_object()
        if lote.estado != "borrador":
            return Response({"detail": "Solo se puede registrar un lote en borrador."}, status=status.HTTP_400_BAD_REQUEST)
        if not lote.muestras.filter(estado_operativo="activa").exists():
            return Response({"detail": "El borrador debe tener al menos una muestra activa."}, status=status.HTTP_400_BAD_REQUEST)
        lote.estado = "registrado"
        lote.save(update_fields=["estado", "fecha_actualizacion"])
        record_operational_event(actor=request.user, action="lote.registrado", entity_type="lote", entity_id=lote.id, entity_label=lote.id, lote=lote, detail="Borrador registrado.", before={"estado": "borrador"}, after={"estado": "registrado"})
        return Response({"id": lote.id, "estado": lote.estado})

    def get_queryset(self):
        queryset = (
            LoteMuestras.objects
            .select_related("cliente_empresa", "usuario_registro", "tipo_gestion")
            .annotate(
                total_muestras_db=Count("muestras", distinct=True),
                muestras_activas_db=Count(
                    "muestras",
                    filter=Q(muestras__estado_operativo="activa"),
                    distinct=True,
                ),
                muestras_ingresadas_db=Count(
                    "muestras",
                    filter=Q(muestras__is_ingresado=True),
                    distinct=True,
                ),
                muestras_resultado_ingresado_db=Count(
                    "muestras",
                    filter=Q(muestras__is_resultado_ingresado=True, muestras__estado_operativo="activa"),
                    distinct=True,
                ),
                muestras_revisadas_db=Count(
                    "muestras",
                    filter=Q(muestras__is_revisado=True),
                    distinct=True,
                ),
                pruebas_asignadas_db=Count(
                    "muestras__resultados",
                    filter=Q(muestras__estado_operativo="activa", muestras__resultados__estado_asignacion="confirmada"),
                    distinct=True,
                ),
                pruebas_completadas_db=Count(
                    "muestras__resultados",
                    filter=Q(
                        muestras__resultados__estado_asignacion="confirmada",
                        muestras__resultados__completada=True,
                        muestras__estado_operativo="activa",
                    ),
                    distinct=True,
                ),
                pruebas_revisadas_db=Count(
                    "muestras__resultados",
                    filter=Q(
                        muestras__resultados__estado_asignacion="confirmada",
                        muestras__resultados__is_revisada=True,
                        muestras__estado_operativo="activa",
                    ),
                    distinct=True,
                ),
                muestras_aceite_db=Count(
                    "muestras",
                    filter=Q(muestras__tipo_muestra="aceite"),
                    distinct=True,
                ),
                muestras_grasa_db=Count(
                    "muestras",
                    filter=Q(muestras__tipo_muestra="grasa"),
                    distinct=True,
                ),
            )
        )
        queryset = queryset.prefetch_related(
            "muestras__referencia_equipo",
            "muestras__asignaciones_punto_muestreo__punto_muestreo",
        )

        user = self.request.user
        queryset = scope_queryset(queryset, user, "cliente_empresa_id")

        if self.action in ["retrieve", "recalcular_estado"]:
            resultados_queryset = (
                PruebaMuestra.objects
                .select_related(
                    "prueba",
                    "prueba__metodo",
                    "prueba__metodo__equipo_prueba",
                )
                .only(
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
                    "prueba__metodo",
                    "prueba__condicion",

                    "prueba__metodo__id",
                    "prueba__metodo__codigo",
                    "prueba__metodo__nombre",
                    "prueba__metodo__norma_referencia",
                    "prueba__metodo__equipo_prueba",

                    "prueba__metodo__equipo_prueba__id",
                    "prueba__metodo__equipo_prueba__codigo",
                    "prueba__metodo__equipo_prueba__nombre",
                )
            )

            queryset = queryset.prefetch_related(
                "muestras",
                "muestras__referencia_equipo",
                "muestras__referencia_equipo__empresa",
                "muestras__asignaciones_punto_muestreo",
                "muestras__asignaciones_punto_muestreo__punto_muestreo",
                "muestras__atributos_tecnicos",
                "muestras__atributos_tecnicos__catalogo",
                "muestras__atributos_tecnicos__item",

                # Nuevos catálogos técnicos de muestra

                Prefetch("muestras__resultados", queryset=resultados_queryset),
            )

        tipo_cliente = self.request.query_params.get("tipo_cliente")
        estado = self.request.query_params.get("estado")
        tipo_gestion = self.request.query_params.get("tipo_gestion")
        fecha_desde = self.request.query_params.get("fecha_desde")
        fecha_hasta = self.request.query_params.get("fecha_hasta")
        search = self.request.query_params.get("search")
        machine_id = self.request.query_params.get("machine_id")
        sampling_point_id = self.request.query_params.get("sampling_point_id")
        client_id = self.request.query_params.get("client_id")

        if tipo_cliente and tipo_cliente != "todos":
            queryset = queryset.filter(tipo_cliente=tipo_cliente)
        if client_id:
            queryset = queryset.filter(cliente_empresa_id=client_id)

        if estado and estado != "todos":
            queryset = queryset.filter(estado=estado)

        if tipo_gestion and tipo_gestion != "todos":
            queryset = queryset.filter(tipo_gestion_id=tipo_gestion)

        if fecha_desde:
            queryset = queryset.filter(fecha_envio__gte=fecha_desde)

        if fecha_hasta:
            queryset = queryset.filter(fecha_envio__lte=fecha_hasta)

        if search:
            queryset = queryset.filter(
                Q(id__icontains=search)
                | Q(cliente_ocasional_nombre__icontains=search)
                | Q(contacto_nombre__icontains=search)
                | Q(cliente_empresa__nombre__icontains=search)
                | Q(muestras__referencia_equipo__nombre__icontains=search)
                | Q(muestras__referencia_equipo__codigo_equipo__icontains=search)
                | Q(muestras__equipo_placa__icontains=search)
                | Q(muestras__asignaciones_punto_muestreo__punto_muestreo__nombre__icontains=search)
            ).distinct()

        match_filter = Q()
        if machine_id:
            match_filter &= Q(muestras__referencia_equipo_id=machine_id)
        if sampling_point_id:
            match_filter &= Q(
                muestras__asignaciones_punto_muestreo__punto_muestreo_id=sampling_point_id,
                muestras__asignaciones_punto_muestreo__activa=True,
            )
        if machine_id or sampling_point_id:
            queryset = queryset.filter(match_filter).annotate(
                muestras_coincidentes_db=Count('muestras', filter=match_filter, distinct=True),
            ).distinct()

        return queryset

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return LoteMuestrasCreateSerializer

        if self.action == "retrieve":
            return LoteMuestrasDetailSerializer

        return LoteMuestrasListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lote = serializer.save()
        record_operational_event(
            actor=request.user,
            action="lote.creado",
            entity_type="lote",
            entity_id=lote.id,
            entity_label=lote.id,
            lote=lote,
            detail="Lote de muestras creado.",
            after=_lot_snapshot(lote),
        )

        response_serializer = LoteMuestrasDetailSerializer(lote, context=self.get_serializer_context())

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        before = _lot_snapshot(serializer.instance)
        lote = serializer.save()
        after = _lot_snapshot(lote)
        if before != after:
            record_operational_event(
                actor=self.request.user,
                action="lote.actualizado",
                entity_type="lote",
                entity_id=lote.id,
                entity_label=lote.id,
                lote=lote,
                detail="Información general del lote actualizada.",
                before=before,
                after=after,
            )

    @action(detail=True, methods=["get"], url_path="timeline")
    def timeline(self, request, pk=None):
        lote = self.get_object()
        queryset = EventoAuditoriaOperativa.objects.filter(lote=lote).select_related(
            "actor", "empresa", "muestra", "prueba_muestra", "reporte", "maquina", "punto_muestreo"
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(EventoAuditoriaOperativaSerializer(page, many=True).data)
        return Response(EventoAuditoriaOperativaSerializer(queryset, many=True).data)

    def destroy(self, request, *args, **kwargs):
        lote = self.get_object()
        if lote.estado != "borrador" or lote.muestras.exists():
            return Response(
                {"detail": "Solo se puede eliminar definitivamente un borrador vacío. Use Cancelar lote para conservar la trazabilidad."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        lote = self.get_object()
        if lote.estado in ["en_laboratorio", "en_analisis", "parcial", "resultados_completos", "revisado", "reportado"]:
            return Response({"detail": "Este lote ya inició procesamiento y no puede cancelarse desde el flujo normal."}, status=status.HTTP_409_CONFLICT)
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return Response({"reason": ["Indique el motivo de cancelación."]}, status=status.HTTP_400_BAD_REQUEST)
        previous_state = lote.estado
        lote.estado = "cancelado"
        lote.motivo_cancelacion = reason
        lote.fecha_cancelacion = timezone.now()
        lote.cancelado_por = request.user
        lote.save(update_fields=["estado", "motivo_cancelacion", "fecha_cancelacion", "cancelado_por", "fecha_actualizacion"])
        audit_user_action(request, "lotes.cancelar", empresa=lote.cliente_empresa, detail=reason, metadata={"lote_id": lote.id})
        record_operational_event(
            actor=request.user,
            action="lote.cancelado",
            entity_type="lote",
            entity_id=lote.id,
            entity_label=lote.id,
            lote=lote,
            detail="Lote cancelado.",
            reason=reason,
            before={"estado": previous_state},
            after={"estado": "cancelado"},
        )
        return Response(LoteMuestrasDetailSerializer(lote, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        lote = self.get_object()
        if lote.estado != "cancelado":
            return Response({"detail": "Solo se pueden reabrir lotes cancelados."}, status=status.HTTP_409_CONFLICT)
        lote.estado = "registrado" if lote.muestras.exists() else "borrador"
        lote.save(update_fields=["estado", "fecha_actualizacion"])
        audit_user_action(request, "lotes.reabrir", empresa=lote.cliente_empresa, metadata={"lote_id": lote.id})
        record_operational_event(
            actor=request.user,
            action="lote.reabierto",
            entity_type="lote",
            entity_id=lote.id,
            entity_label=lote.id,
            lote=lote,
            detail="Lote reabierto.",
            before={"estado": "cancelado"},
            after={"estado": lote.estado},
        )
        return Response(LoteMuestrasDetailSerializer(lote, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="recalcular-estado")
    def recalcular_estado(self, request, pk=None):
        lote = self.get_object()
        lote.recalcular_estado()

        serializer = LoteMuestrasDetailSerializer(lote, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="resumen")
    def resumen(self, request):
        queryset = self.get_queryset()

        data = {
            "total_lotes": queryset.count(),
            "pendientes": queryset.filter(estado__in=["borrador", "registrado"]).count(),
            "en_laboratorio": queryset.filter(estado__in=["en_laboratorio", "en_analisis", "parcial"]).count(),
            "reportados": queryset.filter(estado="reportado").count(),
        }

        return Response(data)

    @action(detail=True, methods=["get", "post"], url_path="samples")
    def samples(self, request, pk=None):
        lote = self.get_object()

        if request.method == "GET":
            queryset = (
                Muestra.objects.filter(lote=lote)
                .select_related("referencia_equipo", "lote__tipo_gestion")
                .prefetch_related("asignaciones_punto_muestreo__punto_muestreo")
                .order_by("-fecha_toma", "-fecha_registro", "-id")
            )
            search = str(request.query_params.get("search") or "").strip()
            machine_id = request.query_params.get("machine_id")
            sampling_point_id = request.query_params.get("sampling_point_id")
            if search:
                queryset = queryset.filter(
                    Q(id__icontains=search)
                    | Q(referencia_equipo__nombre__icontains=search)
                    | Q(referencia_equipo__codigo_equipo__icontains=search)
                    | Q(equipo_placa__icontains=search)
                    | Q(asignaciones_punto_muestreo__punto_muestreo__nombre__icontains=search)
                ).distinct()
            if machine_id:
                queryset = queryset.filter(referencia_equipo_id=machine_id)
            if sampling_point_id:
                queryset = queryset.filter(
                    asignaciones_punto_muestreo__punto_muestreo_id=sampling_point_id,
                    asignaciones_punto_muestreo__activa=True,
                )

            page = self.paginate_queryset(queryset)
            serializer = LoteMuestraWorkspaceSerializer(
                page if page is not None else queryset,
                many=True,
                context={"request": request},
            )
            return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

        if lote.estado == "cancelado":
            return Response(
                {"detail": "No se pueden agregar muestras a un lote cancelado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AddMuestrasToLoteSerializer(
            data=request.data,
            context={
                "request": request,
                "lote": lote,
            },
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        lote.refresh_from_db()
        lote.recalcular_estado()
        record_operational_event(
            actor=request.user,
            action="lote.muestras_agregadas",
            entity_type="lote",
            entity_id=lote.id,
            entity_label=lote.id,
            lote=lote,
            detail="Se agregaron muestras al lote.",
            metadata={"total_muestras": lote.muestras.count()},
        )

        response_serializer = LoteMuestrasDetailSerializer(
            lote,
            context=self.get_serializer_context(),
        )

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
