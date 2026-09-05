from django.db.models import Count, Q
from django.db.models import Prefetch
from rest_framework import filters, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.utils.pagination import StandardResultsSetPagination
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission
from apps.users.api.models.index import User
from apps.users.api.services import audit_user_action
from django.utils import timezone

from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.serializers.loteMuestras.index import (
    LoteMuestrasListSerializer,
    LoteMuestrasDetailSerializer,
    LoteMuestrasCreateSerializer,
     AddMuestrasToLoteSerializer,
)
from apps.dashboard.api.services.operational_center import notify_new_batch


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
        "add_samples": "muestras.crear",
        "cancel": "lotes.eliminar",
        "reopen": "lotes.recalcular_estado",
    }

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

        user = self.request.user
        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            queryset = queryset.filter(cliente_empresa=user.empresa)

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

        if tipo_cliente and tipo_cliente != "todos":
            queryset = queryset.filter(tipo_cliente=tipo_cliente)

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
            )

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
        notify_new_batch(lote)

        response_serializer = LoteMuestrasDetailSerializer(lote, context=self.get_serializer_context())

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

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
        lote.estado = "cancelado"
        lote.motivo_cancelacion = reason
        lote.fecha_cancelacion = timezone.now()
        lote.cancelado_por = request.user
        lote.save(update_fields=["estado", "motivo_cancelacion", "fecha_cancelacion", "cancelado_por", "fecha_actualizacion"])
        audit_user_action(request, "lotes.cancelar", empresa=lote.cliente_empresa, detail=reason, metadata={"lote_id": lote.id})
        return Response(LoteMuestrasDetailSerializer(lote, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        lote = self.get_object()
        if lote.estado != "cancelado":
            return Response({"detail": "Solo se pueden reabrir lotes cancelados."}, status=status.HTTP_409_CONFLICT)
        lote.estado = "registrado" if lote.muestras.exists() else "borrador"
        lote.save(update_fields=["estado", "fecha_actualizacion"])
        audit_user_action(request, "lotes.reabrir", empresa=lote.cliente_empresa, metadata={"lote_id": lote.id})
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

    @action(detail=True, methods=["post"], url_path="samples")
    def add_samples(self, request, pk=None):
        lote = self.get_object()

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

        response_serializer = LoteMuestrasDetailSerializer(
            lote,
            context=self.get_serializer_context(),
        )

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
