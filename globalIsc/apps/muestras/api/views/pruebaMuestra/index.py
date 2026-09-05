from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission
from apps.users.api.models.index import User

from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.services.assignment_sync import synchronize_batch_assignments
from apps.muestras.api.services.workflow import require_batch_operation
from apps.muestras.api.serializers.pruebasMuestra.index import (
    BatchAssignPruebasSerializer,
    CreatePruebaMuestraSerializer,
    PruebaMuestraAssignmentSerializer,
    PruebaMuestraSerializer,
)


class PruebaMuestraViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    queryset = PruebaMuestra.objects.select_related(
        'muestra',
        'muestra__lote',
        'prueba',
        'prueba__metodo',
        'prueba__metodo__equipo_prueba',
        'usuario_solicitud',
        'usuario_medicion',
        'usuario_revision',
        'equipo_configurado',
        'metodo_configurado',
        'condicion_catalogo',
        'condicion_catalogo__unidad',
        'lote_predefinido',
        'criterio_evaluacion',
        'criterio_evaluacion__fuente_limite',
        'criterio_limite_catalogo',
        'criterio_limite_item',
        'criterio_limite_escala',
        'criterio_limite_escala_item',
    )
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "pruebas_muestra.ver",
        "retrieve": "pruebas_muestra.ver",
        "by_sample": "pruebas_muestra.ver",
        "by_batch": "pruebas_muestra.ver",
        "create": "pruebas_muestra.asignar",
        "assign_batch": "pruebas_muestra.asignar_lote",
        "update": "pruebas_muestra.editar",
        "partial_update": "pruebas_muestra.editar",
        "destroy": "pruebas_muestra.eliminar",
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            queryset = queryset.filter(muestra__lote__cliente_empresa=user.empresa)
        lote_id = self.request.query_params.get("lote")
        muestra_id = self.request.query_params.get("muestra")
        estado_asignacion = self.request.query_params.get("estado_asignacion")
        if lote_id:
            queryset = queryset.filter(muestra__lote_id=lote_id)
        if muestra_id:
            queryset = queryset.filter(muestra_id=muestra_id)
        if estado_asignacion:
            queryset = queryset.filter(estado_asignacion=estado_asignacion)
        return queryset

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CreatePruebaMuestraSerializer
        return PruebaMuestraSerializer

    def perform_create(self, serializer):
        if serializer.validated_data["muestra"].estado_operativo != "activa":
            raise ValidationError({"muestra": "No se pueden asignar pruebas a una muestra invalidada."})
        serializer.save(usuario_solicitud=self.request.user)

    def perform_update(self, serializer):
        muestra = serializer.validated_data.get("muestra", serializer.instance.muestra)
        if muestra.estado_operativo != "activa":
            raise ValidationError({"muestra": "No se puede modificar una prueba de una muestra invalidada."})
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        assignment = self.get_object()
        if assignment.completada or assignment.valor not in [None, ""] or assignment.resultados.exists():
            return Response(
                {"detail": "Esta prueba ya tiene mediciones. Corrija o invalide el resultado; no puede desasignarse."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='by-sample/(?P<muestra_id>[^/.]+)')
    def by_sample(self, request, muestra_id=None):
        sample_tests = self.get_queryset().filter(muestra=muestra_id)
        serializer = self.get_serializer(sample_tests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='by-batch/(?P<lote_id>[^/.]+)')
    def by_batch(self, request, lote_id=None):
        sample_tests = self.get_queryset().filter(muestra__lote_id=lote_id).order_by('muestra_id', 'prueba__nombre_variable')
        serializer = PruebaMuestraAssignmentSerializer(
            sample_tests,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='assign-batch')
    def assign_batch(self, request):
        serializer = BatchAssignPruebasSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        lote_queryset = LoteMuestras.objects.prefetch_related('muestras')
        user = request.user
        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            lote_queryset = lote_queryset.filter(cliente_empresa=user.empresa)
        lote = get_object_or_404(lote_queryset, pk=data['lote_id'])
        require_batch_operation(lote, "asignar_pruebas")
        sample_ids = data.get('sample_ids') or []
        muestras_qs = lote.muestras.filter(estado_operativo="activa")
        if sample_ids:
            muestras_qs = muestras_qs.filter(id__in=sample_ids)
        muestras = list(muestras_qs)

        if not muestras:
            return Response({"detail": "El lote no tiene muestras para asignar."}, status=status.HTTP_400_BAD_REQUEST)

        pruebas = data['pruebas']
        estado_asignacion = data['estado_asignacion']
        lote_predefinido = data.get('lote_predefinido')
        sync_result = synchronize_batch_assignments(
            lote=lote,
            muestras=muestras,
            pruebas=pruebas,
            estado_asignacion=estado_asignacion,
            lote_predefinido=lote_predefinido,
            user=request.user,
        )

        response_serializer = PruebaMuestraAssignmentSerializer(
            sync_result.instances[:50],
            many=True,
            context=self.get_serializer_context(),
        )
        return Response({
            'detail': 'Asignación procesada correctamente.',
            'lote': lote.id,
            'samples_count': len(muestras),
            'rows_count': len(pruebas),
            'created_count': sync_result.created,
            'updated_count': sync_result.updated,
            'unchanged_count': sync_result.unchanged,
            'deleted_count': sync_result.deleted,
            'protected_count': len(sync_result.protected),
            'protected_assignment_ids': sync_result.protected,
            'results_preview': response_serializer.data,
        }, status=status.HTTP_200_OK)
