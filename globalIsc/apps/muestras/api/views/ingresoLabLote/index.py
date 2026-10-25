from django.db.models import Count, Q, Prefetch
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission
from apps.users.api.models.index import User
from apps.users.api.data_scope import scope_queryset

from apps.muestras.api.models.ingresoLabLote.index import IngresoLabLote
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.serializers.ingresoLabLote.index import (
    IngresoLabLoteSerializer,
    CreateIngresoLabLoteSerializer,
    LoteDisponibleLaboratorioSerializer,
)
from apps.users.api.services import audit_user_action
from apps.muestras.services.operational_audit import record_operational_event


def muestras_laboratorio_prefetch(lookup="muestras"):
    return Prefetch(
        lookup,
        queryset=(
            Muestra.objects
            .select_related("referencia_equipo")
            .prefetch_related(
                "atributos_tecnicos",
                "atributos_tecnicos__catalogo",
                "atributos_tecnicos__item",
            )
            .order_by("id")
        ),
    )


class IngresoLabLoteViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "laboratorio.ver",
        "retrieve": "laboratorio.ver",
        "available_batches": "laboratorio.ver_lotes_disponibles",
        "create": "laboratorio.ingresar_lote",
        "update": "laboratorio.ingresar_lote",
        "partial_update": "laboratorio.ingresar_lote",
        "destroy": "laboratorio.revertir_ingreso",
    }

    def get_queryset(self):
        queryset = (
            IngresoLabLote.objects
            .select_related("lote", "lote__cliente_empresa", "lote__tipo_gestion", "usuario_recepcion")
            .prefetch_related(muestras_laboratorio_prefetch("lote__muestras"))
            .order_by("-fecha_recepcion", "-fecha_registro")
        )

        user = self.request.user
        queryset = scope_queryset(queryset, user, "lote__cliente_empresa_id")

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(lote_id__icontains=search)
                | Q(lote__cliente_ocasional_nombre__icontains=search)
                | Q(lote__cliente_empresa__nombre__icontains=search)
                | Q(lote__contacto_nombre__icontains=search)
            )

        return queryset

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CreateIngresoLabLoteSerializer
        return IngresoLabLoteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        ingreso = serializer.save()
        record_operational_event(
            actor=request.user,
            action="lote.recibido_laboratorio",
            entity_type="lote",
            entity_id=ingreso.lote_id,
            entity_label=ingreso.lote_id,
            lote=ingreso.lote,
            detail="Lote recibido en laboratorio.",
            after={"estado": ingreso.lote.estado, "fecha_recepcion": str(ingreso.fecha_recepcion)},
        )
        response_serializer = IngresoLabLoteSerializer(ingreso, context=self.get_serializer_context())
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        ingreso = self.get_object()
        lote = ingreso.lote
        has_results = lote.muestras.filter(
            Q(resultados__completada=True)
            | Q(resultados__valor__isnull=False) & ~Q(resultados__valor="")
            | Q(resultados__resultados__isnull=False)
        ).exists()
        has_reports = lote.reportes.exists()
        if has_results or has_reports:
            return Response(
                {"detail": "No se puede revertir el ingreso porque el lote ya tiene resultados o reportes."},
                status=status.HTTP_409_CONFLICT,
            )
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return Response({"reason": ["Indique el motivo de reversión."]}, status=status.HTTP_400_BAD_REQUEST)
        lote.muestras.update(is_ingresado=False)
        lote.estado = "registrado"
        lote.observaciones = "\n".join(filter(None, [lote.observaciones, f"[Reversión de ingreso] {reason}"]))
        lote.save(update_fields=["estado", "observaciones", "fecha_actualizacion"])
        ingreso.delete()
        audit_user_action(request, "laboratorio.revertir_ingreso", empresa=lote.cliente_empresa, detail=reason, metadata={"lote_id": lote.id})
        record_operational_event(
            actor=request.user,
            action="lote.ingreso_laboratorio_revertido",
            entity_type="lote",
            entity_id=lote.id,
            entity_label=lote.id,
            lote=lote,
            detail="Ingreso a laboratorio revertido.",
            reason=reason,
            before={"estado": "en_laboratorio"},
            after={"estado": "registrado"},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="available-batches")
    def available_batches(self, request):
        """
        Lotes disponibles para ingresar al laboratorio.
        Se excluyen los lotes que ya tienen IngresoLabLote o estados posteriores.
        """
        queryset = (
            LoteMuestras.objects
            .select_related("cliente_empresa", "tipo_gestion")
            .prefetch_related(muestras_laboratorio_prefetch())
            .annotate(
                total_muestras_db=Count("muestras", distinct=True),
                muestras_ingresadas_db=Count(
                    "muestras",
                    filter=Q(muestras__is_ingresado=True),
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
            .filter(total_muestras_db__gt=0)
            .exclude(ingreso_lab_lote__isnull=False)
            .exclude(estado__in=[
                "borrador",
                "cancelado",
                "reportado",
                "en_laboratorio",
                "en_analisis",
                "parcial",
                "resultados_completos",
                "revisado",
            ])
            .order_by("-fecha_envio", "-fecha_registro")
        )

        user = request.user
        queryset = scope_queryset(queryset, user, "cliente_empresa_id")

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(id__icontains=search)
                | Q(cliente_ocasional_nombre__icontains=search)
                | Q(cliente_empresa__nombre__icontains=search)
                | Q(contacto_nombre__icontains=search)
            )

        serializer = LoteDisponibleLaboratorioSerializer(queryset, many=True)
        return Response(serializer.data)
