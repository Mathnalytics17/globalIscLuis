import logging
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.utils.pagination import StandardResultsSetPagination
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission
from apps.users.api.models.index import User
from apps.users.api.services import user_has_permission

from apps.activesTree.api.models.index import Carpeta, PuntoMuestreo, AsignacionPuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.misc.api.models.companies.index import Empresa
from apps.muestras.api.models.muestras.index import Muestra

from ..serializers.index import (
    CarpetaSerializer,
    MaquinaConMuestrasSerializer,
    MaquinaSerializer,
    PuntoMuestreoSerializer,
    AsignacionPuntoMuestreoSerializer,
)

logger = logging.getLogger(__name__)


class SyncCompanyRootFolders(APIView):
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite]

    def post(self, request):
        if not (request.user.is_superuser or request.user.role == User.Role.GLOBAL or user_has_permission(request.user, "activos.sincronizar_carpetas")):
            self.permission_denied(request, message="No tiene permisos para sincronizar carpetas.")
        try:
            with transaction.atomic():
                companies = Empresa.objects.filter(is_active=True)
                existing_company_ids = Carpeta.objects.filter(
                    typeFolder='root',
                ).values_list('compania_id', flat=True)
                companies_without_root = companies.exclude(id__in=existing_company_ids)

                created_folders = []
                for company in companies_without_root:
                    folder = Carpeta.objects.create(
                        nombre=company.nombre,
                        typeFolder='root',
                        compania=company,
                        id_parent_node='-1',
                        isMachine=False,
                        is_pt_medida=False,
                    )
                    created_folders.append({
                        'id': folder.id,
                        'nombre': folder.nombre,
                        'empresa_id': company.id,
                        'empresa_nombre': company.nombre,
                    })

                return Response({
                    'success': True,
                    'message': f'Se crearon {len(created_folders)} carpetas root',
                    'created_folders': created_folders,
                    'total_empresas': companies.count(),
                    'empresas_sin_carpeta': len(created_folders),
                })
        except Exception as exc:
            logger.exception('Error sincronizando carpetas root')
            return Response({
                'success': False,
                'error': str(exc),
                'message': 'Error al sincronizar carpetas root',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FolderViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    queryset = Carpeta.objects.select_related('compania', 'machine', 'muestra')
    serializer_class = CarpetaSerializer
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "activos.ver",
        "retrieve": "activos.ver",
        "create": "activos.crear_carpeta",
        "update": "activos.editar_carpeta",
        "partial_update": "activos.editar_carpeta",
        "destroy": "activos.eliminar_carpeta",
    }
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['compania_id', 'typeFolder']

    def get_queryset(self):
        queryset = self.queryset
        user = self.request.user
        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            queryset = queryset.filter(compania=user.empresa)
        nombre = self.request.query_params.get('nombre')
        if nombre:
            queryset = queryset.filter(nombre=nombre)
        return queryset

    def destroy(self, request, *args, **kwargs):
        folder = self.get_object()
        if folder.typeFolder == 'root' or str(folder.id_parent_node) == '-1':
            return Response(
                {'detail': 'La carpeta raíz de una empresa no se puede eliminar.'},
                status=status.HTTP_409_CONFLICT,
            )
        if Carpeta.objects.filter(id_parent_node=str(folder.id)).exists():
            return Response(
                {'detail': 'No se puede eliminar una carpeta que contiene elementos.'},
                status=status.HTTP_409_CONFLICT,
            )
        if folder.machine_id:
            return Response(
                {'detail': 'Elimine la maquina asociada desde el endpoint de maquinas.'},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


class MaquinaViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    queryset = Maquina.objects.select_related('empresa')
    serializer_class = MaquinaSerializer
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "maquinas.ver",
        "retrieve": "maquinas.ver",
        "create": "maquinas.crear",
        "update": "maquinas.editar",
        "partial_update": "maquinas.editar",
        "destroy": "maquinas.eliminar",
        "reactivate": "maquinas.editar",
    }
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['empresa', 'nombre', 'tipoAceite', 'numero_serie', 'activo']
    search_fields = ['nombre', 'codigo_equipo', 'numero_serie']
    ordering_fields = ['nombre', 'codigo_equipo', 'numero_serie']
    ordering = ['nombre']

    def get_queryset(self):
        queryset = self.queryset
        user = self.request.user
        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            queryset = queryset.filter(empresa=user.empresa)
        if self.action != 'reactivate' and self.request.query_params.get('include_inactive') not in ['1', 'true', 'True']:
            queryset = queryset.filter(activo=True)
        if self.request.query_params.get('include_muestras') in ['1', 'true', 'True']:
            queryset = queryset.prefetch_related(
                'muestra_set',
                'muestra_set__referencia_equipo',
                'muestra_set__referencia_equipo__empresa',
                'muestra_set__resultados',
                'muestra_set__resultados__prueba',
            )
        return queryset

    def get_serializer_class(self):
        if self.request.query_params.get('include_muestras') in ['1', 'true', 'True']:
            return MaquinaConMuestrasSerializer
        return MaquinaSerializer

    def destroy(self, request, *args, **kwargs):
        machine = self.get_object()
        machine.activo = False
        machine.save(update_fields=['activo'])
        machine.puntos_muestreo.update(activo=False)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='reactivate')
    def reactivate(self, request, pk=None):
        machine = self.get_object()
        machine.activo = True
        machine.save(update_fields=['activo'])
        return Response(self.get_serializer(machine).data)


class PuntoMuestreoViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    serializer_class = PuntoMuestreoSerializer
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        'list': 'activos.ver',
        'retrieve': 'activos.ver',
        'create': 'activos.gestionar_puntos',
        'update': 'activos.gestionar_puntos',
        'partial_update': 'activos.gestionar_puntos',
        'destroy': 'activos.gestionar_puntos',
        'organize': 'activos.asignar_puntos',
        'reactivate': 'activos.gestionar_puntos',
    }

    def get_queryset(self):
        queryset = PuntoMuestreo.objects.select_related('maquina', 'maquina__empresa').annotate(
            muestras_asociadas=Count('asignaciones', filter=Q(asignaciones__activa=True)),
        )
        user = self.request.user
        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            queryset = queryset.filter(maquina__empresa=user.empresa)
        machine = self.request.query_params.get('machine')
        if machine:
            queryset = queryset.filter(maquina_id=machine)
        if self.action != 'reactivate' and self.request.query_params.get('include_inactive') not in ('1', 'true', 'True'):
            queryset = queryset.filter(activo=True)
        return queryset

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

    def destroy(self, request, *args, **kwargs):
        point = self.get_object()
        if point.asignaciones.filter(activa=True).exists():
            return Response(
                {'detail': 'No se puede desactivar un punto con muestras asociadas. Reasignelas primero.'},
                status=status.HTTP_409_CONFLICT,
            )
        point.activo = False
        point.save(update_fields=['activo', 'actualizado_en'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='reactivate')
    def reactivate(self, request, pk=None):
        point = self.get_object()
        if not point.maquina.activo:
            return Response({'detail': 'Reactive primero la máquina.'}, status=status.HTTP_409_CONFLICT)
        point.activo = True
        point.save(update_fields=['activo', 'actualizado_en'])
        return Response(self.get_serializer(point).data)

    @action(detail=True, methods=['post'], url_path='organize')
    def organize(self, request, pk=None):
        point = self.get_object()
        if not point.activo:
            return Response({'detail': 'El punto de muestreo esta inactivo.'}, status=status.HTTP_409_CONFLICT)

        sample_ids = set(str(item) for item in (request.data.get('sample_ids') or []) if item)
        lote_id = request.data.get('lote_id')
        candidates = Muestra.objects.select_related('lote', 'referencia_equipo')
        selector = Q(id__in=sample_ids)
        if lote_id:
            selector |= Q(lote_id=lote_id)
        if not sample_ids and not lote_id:
            return Response({'detail': 'Indique sample_ids o lote_id.'}, status=status.HTTP_400_BAD_REQUEST)
        candidates = list(candidates.filter(selector).distinct())

        user = request.user
        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            if point.maquina.empresa_id != getattr(user, 'empresa_id', None):
                self.permission_denied(request)
            candidates = [item for item in candidates if item.referencia_equipo and item.referencia_equipo.empresa_id == user.empresa_id]

        eligible = [item for item in candidates if item.referencia_equipo_id == point.maquina_id]
        incompatible = [
            {'muestra': item.id, 'maquina_id': item.referencia_equipo_id, 'motivo': 'La muestra no pertenece a la maquina del punto.'}
            for item in candidates if item.referencia_equipo_id != point.maquina_id
        ]
        assigned = []
        unchanged = []
        with transaction.atomic():
            for sample in eligible:
                current = AsignacionPuntoMuestreo.objects.filter(muestra=sample, activa=True).first()
                if current and current.punto_muestreo_id == point.id:
                    unchanged.append(sample.id)
                    continue
                if current:
                    current.activa = False
                    current.finalizado_en = timezone.now()
                    current.save(update_fields=['activa', 'finalizado_en'])
                AsignacionPuntoMuestreo.objects.create(
                    muestra=sample,
                    punto_muestreo=point,
                    origen='lote' if lote_id else 'manual',
                    asignado_por=user,
                )
                assigned.append(sample.id)

        return Response({
            'punto_muestreo': point.id,
            'solicitadas': len(candidates),
            'asignadas': assigned,
            'sin_cambios': unchanged,
            'omitidas': incompatible,
            'resumen': {
                'asignadas': len(assigned),
                'sin_cambios': len(unchanged),
                'omitidas': len(incompatible),
            },
        })


class AsignacionPuntoMuestreoViewSet(ActionPermissionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AsignacionPuntoMuestreoSerializer
    permission_classes = [IsAuthenticated, HasSecurityPermission]
    permission_action_map = {'list': 'activos.ver', 'retrieve': 'activos.ver'}

    def get_queryset(self):
        queryset = AsignacionPuntoMuestreo.objects.select_related(
            'muestra', 'muestra__lote', 'punto_muestreo', 'punto_muestreo__maquina',
        )
        user = self.request.user
        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            queryset = queryset.filter(punto_muestreo__maquina__empresa=user.empresa)
        if self.request.query_params.get('active', 'true').lower() != 'all':
            queryset = queryset.filter(activa=self.request.query_params.get('active', 'true').lower() == 'true')
        if self.request.query_params.get('point'):
            queryset = queryset.filter(punto_muestreo_id=self.request.query_params['point'])
        if self.request.query_params.get('machine'):
            queryset = queryset.filter(punto_muestreo__maquina_id=self.request.query_params['machine'])
        if self.request.query_params.get('batch'):
            queryset = queryset.filter(muestra__lote_id=self.request.query_params['batch'])
        return queryset
