import logging
import json
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.utils.pagination import StandardResultsSetPagination
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission
from apps.users.api.models.index import User
from apps.users.api.data_scope import can_access_company, scope_queryset

from apps.activesTree.api.models.index import Carpeta, PuntoMuestreo, AsignacionPuntoMuestreo, Lubricante
from apps.activesTree.api.models.machines.index import Maquina
from apps.activesTree.services import ensure_machine_tree_node
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.resultado.api.models.index import Resultado
from apps.muestras.api.models.auditoria import EventoAuditoriaOperativa
from apps.muestras.api.serializers.auditoria import EventoAuditoriaOperativaSerializer
from apps.muestras.services.operational_audit import record_operational_event

from ..serializers.index import (
    CarpetaSerializer,
    MaquinaConMuestrasSerializer,
    MaquinaSerializer,
    PuntoMuestreoSerializer,
    AsignacionPuntoMuestreoSerializer,
    LubricanteSerializer,
)

logger = logging.getLogger(__name__)


def _asset_snapshot(instance, fields):
    """Valores serializables y relevantes para comparar un activo."""
    return {field: getattr(instance, field) for field in fields}


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
        queryset = scope_queryset(queryset, user, "compania_id")
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
        if folder.machine_id and folder.machine.activo:
            return Response(
                {'detail': 'Elimine la maquina asociada desde el endpoint de maquinas.'},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """The company root is a projection of Empresa.nombre, never a folder.

        Keeping this rule on the API (rather than only hiding an action in the
        UI) prevents a stale client or direct request from splitting the name
        shown in the asset tree from the actual company name.
        """
        folder = self.get_object()
        if folder.typeFolder == 'root' or str(folder.id_parent_node) == '-1':
            return Response(
                {
                    'detail': (
                        'El nodo raíz representa a la empresa y no se puede editar como carpeta. '
                        'Cambie el nombre desde los datos de la empresa.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)


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
        "activity": "maquinas.ver",
        "history": "maquinas.ver",
    }
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['empresa', 'nombre', 'tipoAceite', 'numero_serie', 'activo']
    search_fields = ['nombre', 'codigo_equipo', 'numero_serie']
    ordering_fields = ['nombre', 'codigo_equipo', 'numero_serie']
    ordering = ['nombre']

    def get_queryset(self):
        queryset = self.queryset
        user = self.request.user
        queryset = scope_queryset(queryset, user, "empresa_id")
        if self.action != 'reactivate' and self.request.query_params.get('include_inactive') not in ['1', 'true', 'True']:
            queryset = queryset.filter(activo=True)
        if self.request.query_params.get('include_muestras') in ['1', 'true', 'True']:
            queryset = queryset.prefetch_related(
                'muestra_set',
                'muestra_set__referencia_equipo',
                # La muestra conserva su punto de medición: un equipo puede tener
                # varios circuitos y mezclar sus tendencias daría una lectura falsa.
                'muestra_set__asignaciones_punto_muestreo__punto_muestreo',
                'muestra_set__referencia_equipo__empresa',
                'muestra_set__resultados',
                'muestra_set__resultados__resultados',
                'muestra_set__resultados__prueba',
            )
        return queryset

    def get_serializer_class(self):
        if self.request.query_params.get('include_muestras') in ['1', 'true', 'True']:
            return MaquinaConMuestrasSerializer
        return MaquinaSerializer

    @staticmethod
    def _audit_snapshot(machine):
        return _asset_snapshot(machine, (
            "nombre", "codigo_equipo", "numero_serie", "descripcion", "componente",
            "tipoAceite", "frecuenciaCambio", "frecuenciaAnalisis", "activo", "empresa_id",
        ))

    def perform_create(self, serializer):
        # La máquina y su nodo visual deben nacer juntos. Antes el frontend
        # creaba la máquina (que quedaba en la raíz) y luego intentaba moverla
        # creando otro nodo, dejando un activo mal ubicado si esa segunda
        # solicitud fallaba.
        with transaction.atomic():
            machine = serializer.save()
            ensure_machine_tree_node(machine, parent_folder=serializer.parent_folder)
            record_operational_event(
                actor=self.request.user,
                action="maquina.creada",
                entity_type="maquina",
                entity_id=machine.id,
                entity_label=machine.nombre,
                maquina=machine,
                detail="Máquina creada.",
                after=self._audit_snapshot(machine),
            )

    def perform_update(self, serializer):
        before = self._audit_snapshot(serializer.instance)
        machine = serializer.save()
        after = self._audit_snapshot(machine)
        if before != after:
            record_operational_event(
                actor=self.request.user,
                action="maquina.actualizada",
                entity_type="maquina",
                entity_id=machine.id,
                entity_label=machine.nombre,
                maquina=machine,
                detail="Ficha técnica de máquina actualizada.",
                before=before,
                after=after,
            )

    def destroy(self, request, *args, **kwargs):
        machine = self.get_object()
        before = self._audit_snapshot(machine)
        machine.activo = False
        machine.save(update_fields=['activo'])
        machine.puntos_muestreo.update(activo=False)
        record_operational_event(
            actor=request.user,
            action="maquina.desactivada",
            entity_type="maquina",
            entity_id=machine.id,
            entity_label=machine.nombre,
            maquina=machine,
            detail="Máquina desactivada junto con sus puntos de medición.",
            before=before,
            after={**before, "activo": False},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='reactivate')
    def reactivate(self, request, pk=None):
        machine = self.get_object()
        before = self._audit_snapshot(machine)
        machine.activo = True
        machine.save(update_fields=['activo'])
        ensure_machine_tree_node(machine)
        record_operational_event(
            actor=request.user,
            action="maquina.reactivada",
            entity_type="maquina",
            entity_id=machine.id,
            entity_label=machine.nombre,
            maquina=machine,
            detail="Máquina reactivada.",
            before=before,
            after=self._audit_snapshot(machine),
        )
        return Response(self.get_serializer(machine).data)

    @action(detail=True, methods=['get'], url_path='activity')
    def activity(self, request, pk=None):
        machine = self.get_object()
        queryset = EventoAuditoriaOperativa.objects.filter(maquina=machine).select_related(
            "actor", "empresa", "lote", "muestra", "prueba_muestra", "reporte", "punto_muestreo"
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(EventoAuditoriaOperativaSerializer(page, many=True).data)
        return Response(EventoAuditoriaOperativaSerializer(queryset, many=True).data)

    @staticmethod
    def _history_rows(assignment):
        """Aplana el resultado dinámico en filas que se puedan graficar sin
        descargar todas las muestras del equipo al navegador."""
        sample = assignment.muestra
        point_assignments = getattr(sample, "active_point_assignments", [])
        point = point_assignments[0].punto_muestreo if point_assignments else None
        results = list(getattr(assignment, "history_resultados", []))
        result = results[0] if results else None
        if not result:
            return []
        try:
            payload = json.loads(result.resultado) if isinstance(result.resultado, str) else (result.resultado or {})
        except (TypeError, ValueError):
            payload = {}
        fields = {str(field.get("key")): field for field in payload.get("fields", []) if isinstance(field, dict)}
        values = [value for value in payload.get("values", []) if isinstance(value, dict)]
        base = {
            "machineId": str(sample.referencia_equipo_id),
            "machineName": sample.referencia_equipo.nombre,
            "pointId": str(point.id) if point else "",
            "pointName": point.nombre if point else "Sin punto de medición",
            "sampleId": sample.id,
            "date": sample.fecha_toma or result.fecha_medicion or result.fecha_registro,
            "testId": str(assignment.prueba_id),
            "testName": f"{assignment.prueba.acronimo} - {assignment.prueba.nombre_variable}",
            "status": assignment.estado_limite or (assignment.evaluacion_limite or {}).get("estado") or "-",
        }
        rows = []
        for index, value in enumerate(values):
            field = fields.get(str(value.get("key")), {})
            raw_value = value.get("value_label", value.get("value"))
            rows.append({
                **base,
                "id": f"{assignment.id}-{result.id}-{index}",
                "seriesId": f"{assignment.prueba_id}-{field.get('key') or value.get('key') or index}",
                "resultName": field.get("resultado_nombre") or "Resultado principal",
                "fieldName": field.get("componente_nombre") or field.get("label") or value.get("key") or "Resultado",
                "dataType": field.get("tipo_dato") or "",
                "value": raw_value,
                "unit": field.get("unidad") or assignment.unidad or assignment.prueba.unidad_medida or "",
                "status": value.get("estado") or base["status"],
            })
        if rows:
            return rows
        return [{
            **base,
            "id": f"{assignment.id}-{result.id}-principal",
            "seriesId": f"{assignment.prueba_id}-principal",
            "resultName": "Resultado principal",
            "fieldName": "Resultado",
            "dataType": "",
            "value": assignment.valor,
            "unit": assignment.unidad or assignment.prueba.unidad_medida or "",
        }]

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        machine = self.get_object()
        point_id = request.query_params.get("point")
        test_id = request.query_params.get("test")
        include_invalid = request.query_params.get("include_invalid") in {"1", "true", "True"}
        assignments = PruebaMuestra.objects.filter(
            muestra__referencia_equipo=machine,
            estado_asignacion="confirmada",
        ).select_related("muestra", "muestra__referencia_equipo", "prueba").prefetch_related(
            Prefetch(
                "muestra__asignaciones_punto_muestreo",
                queryset=AsignacionPuntoMuestreo.objects.filter(activa=True).select_related("punto_muestreo"),
                to_attr="active_point_assignments",
            ),
            Prefetch("resultados", queryset=Resultado.objects.order_by("-fecha_actualizacion", "-id"), to_attr="history_resultados"),
        )
        if not include_invalid:
            assignments = assignments.filter(muestra__estado_operativo="activa")
        if point_id:
            assignments = assignments.filter(muestra__asignaciones_punto_muestreo__punto_muestreo_id=point_id, muestra__asignaciones_punto_muestreo__activa=True)
        if test_id:
            assignments = assignments.filter(prueba_id=test_id)
        assignments = assignments.order_by("muestra__fecha_toma", "muestra_id", "id")
        page = self.paginate_queryset(assignments)
        selected = page if page is not None else assignments
        rows = [row for assignment in selected for row in self._history_rows(assignment)]
        if page is not None:
            return self.get_paginated_response(rows)
        return Response(rows)


class PuntoMuestreoViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
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
        'activity': 'activos.ver',
    }

    def get_queryset(self):
        queryset = PuntoMuestreo.objects.select_related('maquina', 'maquina__empresa', 'lubricante_catalogo').annotate(
            muestras_asociadas=Count('asignaciones', filter=Q(asignaciones__activa=True)),
        )
        user = self.request.user
        queryset = scope_queryset(queryset, user, "maquina__empresa_id")
        machine = self.request.query_params.get('machine')
        if machine:
            queryset = queryset.filter(maquina_id=machine)
        if self.action != 'reactivate' and self.request.query_params.get('include_inactive') not in ('1', 'true', 'True'):
            queryset = queryset.filter(activo=True)
        return queryset

    def perform_create(self, serializer):
        point = serializer.save(creado_por=self.request.user)
        record_operational_event(
            actor=self.request.user,
            action="punto_muestreo.creado",
            entity_type="punto_muestreo",
            entity_id=point.id,
            entity_label=point.nombre,
            maquina=point.maquina,
            punto_muestreo=point,
            detail="Punto de medición creado.",
            after=self._audit_snapshot(point),
        )

    @staticmethod
    def _audit_snapshot(point):
        return _asset_snapshot(point, (
            "nombre", "codigo", "descripcion", "lubricante", "lubricante_catalogo_id",
            "frecuencia_cambio", "unidad_frecuencia_cambio", "frecuencia_analisis",
            "unidad_frecuencia_analisis", "activo", "maquina_id",
        ))

    def perform_update(self, serializer):
        before = self._audit_snapshot(serializer.instance)
        point = serializer.save()
        after = self._audit_snapshot(point)
        if before != after:
            record_operational_event(
                actor=self.request.user,
                action="punto_muestreo.actualizado",
                entity_type="punto_muestreo",
                entity_id=point.id,
                entity_label=point.nombre,
                maquina=point.maquina,
                punto_muestreo=point,
                detail="Configuración del punto de medición actualizada.",
                before=before,
                after=after,
            )

    def destroy(self, request, *args, **kwargs):
        point = self.get_object()
        if point.asignaciones.filter(activa=True).exists():
            return Response(
                {'detail': 'No se puede desactivar un punto con muestras asociadas. Reasignelas primero.'},
                status=status.HTTP_409_CONFLICT,
            )
        before = self._audit_snapshot(point)
        point.activo = False
        point.save(update_fields=['activo', 'actualizado_en'])
        record_operational_event(
            actor=request.user,
            action="punto_muestreo.desactivado",
            entity_type="punto_muestreo",
            entity_id=point.id,
            entity_label=point.nombre,
            maquina=point.maquina,
            punto_muestreo=point,
            detail="Punto de medición desactivado.",
            before=before,
            after={**before, "activo": False},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='reactivate')
    def reactivate(self, request, pk=None):
        point = self.get_object()
        if not point.maquina.activo:
            return Response({'detail': 'Reactive primero la máquina.'}, status=status.HTTP_409_CONFLICT)
        before = self._audit_snapshot(point)
        point.activo = True
        point.save(update_fields=['activo', 'actualizado_en'])
        record_operational_event(
            actor=request.user,
            action="punto_muestreo.reactivado",
            entity_type="punto_muestreo",
            entity_id=point.id,
            entity_label=point.nombre,
            maquina=point.maquina,
            punto_muestreo=point,
            detail="Punto de medición reactivado.",
            before=before,
            after=self._audit_snapshot(point),
        )
        return Response(self.get_serializer(point).data)

    @action(detail=True, methods=['get'], url_path='activity')
    def activity(self, request, pk=None):
        point = self.get_object()
        queryset = EventoAuditoriaOperativa.objects.filter(punto_muestreo=point).select_related(
            "actor", "empresa", "lote", "muestra", "prueba_muestra", "reporte", "maquina"
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(EventoAuditoriaOperativaSerializer(page, many=True).data)
        return Response(EventoAuditoriaOperativaSerializer(queryset, many=True).data)

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
        if not can_access_company(user, point.maquina.empresa_id):
            self.permission_denied(request)
        candidates = [
            item for item in candidates
            if item.referencia_equipo and can_access_company(user, item.referencia_equipo.empresa_id)
        ]

        eligible = [item for item in candidates if item.referencia_equipo_id == point.maquina_id]
        incompatible = [
            {'muestra': item.id, 'maquina_id': item.referencia_equipo_id, 'motivo': 'La muestra no pertenece a la maquina del punto.'}
            for item in candidates if item.referencia_equipo_id != point.maquina_id
        ]
        assigned = []
        unchanged = []
        with transaction.atomic():
            for sample in eligible:
                current = (
                    AsignacionPuntoMuestreo.objects.filter(muestra=sample, activa=True)
                    .select_related('punto_muestreo')
                    .first()
                )
                if current and current.punto_muestreo_id == point.id:
                    unchanged.append(sample.id)
                    continue
                previous_point = {
                    "id": current.punto_muestreo_id,
                    "nombre": current.punto_muestreo.nombre,
                } if current else None
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
                record_operational_event(
                    actor=user,
                    action="muestra.punto_muestreo_asignado",
                    entity_type="muestra",
                    entity_id=sample.id,
                    entity_label=sample.id,
                    muestra=sample,
                    maquina=point.maquina,
                    punto_muestreo=point,
                    detail="Muestra asociada a un punto de medición.",
                    before={"punto_muestreo": previous_point} if previous_point else {},
                    after={"punto_muestreo": {"id": point.id, "nombre": point.nombre}},
                    metadata={"origen_asignacion": "lote" if lote_id else "manual"},
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


class LubricanteViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    serializer_class = LubricanteSerializer
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    # Alta rápida desde recepción: quien puede crear muestras puede registrar el
    # lubricante que llegó. La edición de puntos sigue siendo un permiso aparte.
    permission_action_map = {
        'list': 'activos.ver', 'retrieve': 'activos.ver',
        'create': 'muestras.crear', 'update': 'activos.gestionar_puntos',
        'partial_update': 'activos.gestionar_puntos', 'destroy': 'activos.gestionar_puntos',
    }

    def get_queryset(self):
        queryset = Lubricante.objects.all()
        if self.request.query_params.get('include_inactive') not in ('1', 'true', 'True'):
            queryset = queryset.filter(activo=True)
        return queryset


class AsignacionPuntoMuestreoViewSet(ActionPermissionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AsignacionPuntoMuestreoSerializer
    permission_classes = [IsAuthenticated, HasSecurityPermission]
    permission_action_map = {'list': 'activos.ver', 'retrieve': 'activos.ver'}

    def get_queryset(self):
        queryset = AsignacionPuntoMuestreo.objects.select_related(
            'muestra', 'muestra__lote', 'punto_muestreo', 'punto_muestreo__maquina',
        )
        user = self.request.user
        queryset = scope_queryset(queryset, user, "punto_muestreo__maquina__empresa_id")
        if self.request.query_params.get('active', 'true').lower() != 'all':
            queryset = queryset.filter(activa=self.request.query_params.get('active', 'true').lower() == 'true')
        if self.request.query_params.get('point'):
            queryset = queryset.filter(punto_muestreo_id=self.request.query_params['point'])
        if self.request.query_params.get('machine'):
            queryset = queryset.filter(punto_muestreo__maquina_id=self.request.query_params['machine'])
        if self.request.query_params.get('batch'):
            queryset = queryset.filter(muestra__lote_id=self.request.query_params['batch'])
        return queryset
