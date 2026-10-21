from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission
from apps.muestras.services.operational_audit import record_operational_event

from apps.misc.api.models.technicalCatalogs.index import (
    CategoriaUnidad,
    Condicion,
    EquipoPrueba,
    MetodoEquipo,
    Unidad,
)
from apps.misc.api.serializers.technicalCatalogs.index import (
    CategoriaUnidadSerializer,
    CondicionSerializer,
    EquipoPruebaSerializer,
    MetodoEquipoSerializer,
    UnidadSerializer,
)


class BaseTechnicalCatalogViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ["nombre", "codigo", "created_at", "updated_at"]

    def _snapshot(self, instance):
        return self.get_serializer(instance).data

    def _record_event(self, instance, action, detail, before=None, after=None):
        record_operational_event(
            actor=self.request.user,
            action=action,
            entity_type=f"configuracion.{instance._meta.model_name}",
            entity_id=instance.pk,
            entity_label=str(instance),
            detail=detail,
            before=before or {},
            after=after or {},
        )

    def perform_create(self, serializer):
        instance = serializer.save()
        self._record_event(instance, f"configuracion.{instance._meta.model_name}.creada", "Catálogo técnico creado.", after=self._snapshot(instance))

    def perform_update(self, serializer):
        before = self._snapshot(serializer.instance)
        instance = serializer.save()
        after = self._snapshot(instance)
        if before != after:
            self._record_event(instance, f"configuracion.{instance._meta.model_name}.actualizada", "Catálogo técnico actualizado.", before, after)

    def get_queryset(self):
        queryset = super().get_queryset()
        activo = self.request.query_params.get("activo")

        if activo is not None:
            queryset = queryset.filter(activo=activo.lower() in ["1", "true", "yes"])

        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        before = self._snapshot(instance)
        instance.activo = False
        instance.save(update_fields=["activo", "updated_at"])
        self._record_event(instance, f"configuracion.{instance._meta.model_name}.desactivada", "Catálogo técnico desactivado.", before, self._snapshot(instance))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        instance = self.get_object()
        before = self._snapshot(instance)
        instance.activo = True
        instance.save(update_fields=["activo", "updated_at"])
        self._record_event(instance, f"configuracion.{instance._meta.model_name}.reactivada", "Catálogo técnico reactivado.", before, self._snapshot(instance))
        return Response(self.get_serializer(instance).data)


class EquipoPruebaViewSet(BaseTechnicalCatalogViewSet):
    permission_action_map = {
        "list": "equipos_prueba.ver",
        "retrieve": "equipos_prueba.ver",
        "create": "equipos_prueba.crear",
        "update": "equipos_prueba.editar",
        "partial_update": "equipos_prueba.editar",
        "destroy": "equipos_prueba.eliminar",
        "reactivate": "equipos_prueba.editar",
    }
    queryset = EquipoPrueba.objects.all()
    serializer_class = EquipoPruebaSerializer
    search_fields = ["codigo", "nombre", "descripcion"]


class UnidadViewSet(BaseTechnicalCatalogViewSet):
    permission_action_map = {
        "list": "unidades.ver",
        "retrieve": "unidades.ver",
        "create": "unidades.crear",
        "update": "unidades.editar",
        "partial_update": "unidades.editar",
        "destroy": "unidades.eliminar",
        "reactivate": "unidades.editar",
    }
    queryset = Unidad.objects.select_related("categoria")
    serializer_class = UnidadSerializer
    search_fields = ["nombre", "simbolo", "magnitud", "categoria__nombre", "descripcion"]


class CategoriaUnidadViewSet(BaseTechnicalCatalogViewSet):
    """Managed unit categories; shared by units instead of free-text labels."""

    permission_action_map = {
        "list": "unidades.ver",
        "retrieve": "unidades.ver",
        "create": "unidades.crear",
        "update": "unidades.editar",
        "partial_update": "unidades.editar",
        "destroy": "unidades.eliminar",
        "reactivate": "unidades.editar",
    }
    queryset = CategoriaUnidad.objects.all()
    serializer_class = CategoriaUnidadSerializer
    search_fields = ["nombre", "descripcion"]

    def perform_update(self, serializer):
        before = self._snapshot(serializer.instance)
        instance = serializer.save()
        # `magnitud` remains a compatibility label. Renaming a category must
        # never leave old labels attached to the units that reference it.
        if before.get("nombre") != instance.nombre:
            Unidad.objects.filter(categoria=instance).update(magnitud=instance.nombre)
        after = self._snapshot(instance)
        if before != after:
            self._record_event(instance, "configuracion.categoriaunidad.actualizada", "Categoría de unidad actualizada.", before, after)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.unidades.filter(activo=True).exists():
            return Response(
                {"detail": "No puede desactivar una categoría mientras tenga unidades activas. Reasigne o desactive esas unidades primero."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


class MetodoEquipoViewSet(BaseTechnicalCatalogViewSet):
    permission_action_map = {
        "list": "equipos_prueba.ver",
        "retrieve": "equipos_prueba.ver",
        "create": "equipos_prueba.crear",
        "update": "equipos_prueba.editar",
        "partial_update": "equipos_prueba.editar",
        "destroy": "equipos_prueba.eliminar",
        "reactivate": "equipos_prueba.editar",
    }
    queryset = MetodoEquipo.objects.select_related("equipo_prueba")
    serializer_class = MetodoEquipoSerializer
    search_fields = ["codigo", "nombre", "norma_referencia", "descripcion"]

    def get_queryset(self):
        queryset = super().get_queryset()
        equipo_prueba = self.request.query_params.get("equipo_prueba")

        if equipo_prueba:
            queryset = queryset.filter(equipo_prueba_id=equipo_prueba)

        return queryset


class CondicionViewSet(BaseTechnicalCatalogViewSet):
    permission_action_map = {
        "list": "condiciones.ver",
        "retrieve": "condiciones.ver",
        "create": "condiciones.crear",
        "update": "condiciones.editar",
        "partial_update": "condiciones.editar",
        "destroy": "condiciones.eliminar",
        "reactivate": "condiciones.editar",
    }
    queryset = Condicion.objects.select_related("unidad", "magnitud_categoria")
    serializer_class = CondicionSerializer
    search_fields = ["nombre", "magnitud", "magnitud_categoria__nombre", "descripcion", "unidad__simbolo"]

    def get_queryset(self):
        queryset = super().get_queryset()
        magnitud_categoria = self.request.query_params.get("magnitud_categoria")
        magnitud = self.request.query_params.get("magnitud")

        if magnitud_categoria:
            queryset = queryset.filter(magnitud_categoria_id=magnitud_categoria)
        elif magnitud:
            # Legacy query parameter: retain it as a case-insensitive label
            # filter while the foreign key is the source of truth.
            queryset = queryset.filter(magnitud_categoria__nombre__iexact=magnitud)

        return queryset
