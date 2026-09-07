from django.urls import include, path

from .views.companies.index import EmpresaViewSet
from .views.dynamicTechnicalConfig.index import PruebaLimiteCampoViewSet
from .views.pruebas.index import PruebaViewSet
from .views.technicalCatalogs.index import CondicionViewSet, EquipoPruebaViewSet, MetodoEquipoViewSet, UnidadViewSet


urlpatterns = [
    path("", include("apps.misc.api.urls_technical_config")),
    path("companies/", EmpresaViewSet.as_view({"get": "list", "post": "create"}), name="companies-list"),
    path("companies/estadisticas/", EmpresaViewSet.as_view({"get": "estadisticas"}), name="companies-stats"),
    path("companies/buscar/", EmpresaViewSet.as_view({"get": "buscar"}), name="companies-search"),
    path("companies/<int:pk>/", EmpresaViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="companies-detail"),
    path("companies/<int:pk>/informacion-completa/", EmpresaViewSet.as_view({"get": "informacion_completa"}), name="companies-full-info"),
    path("companies/<int:pk>/block/", EmpresaViewSet.as_view({"post": "block"}), name="companies-block"),
    path("companies/<int:pk>/read-only/", EmpresaViewSet.as_view({"post": "read_only"}), name="companies-read-only"),
    path("companies/<int:pk>/restore-active/", EmpresaViewSet.as_view({"post": "restore_active"}), name="companies-restore-active"),
    path("companies/<int:pk>/invite-admin/", EmpresaViewSet.as_view({"post": "invite_admin"}), name="companies-invite-admin"),
    path("technical-catalogs/test-equipment/", EquipoPruebaViewSet.as_view({"get": "list", "post": "create"}), name="test-equipment-list"),
    path("technical-catalogs/test-equipment/<int:pk>/", EquipoPruebaViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="test-equipment-detail"),
    path("technical-catalogs/test-equipment/<int:pk>/reactivate/", EquipoPruebaViewSet.as_view({"post": "reactivate"}), name="test-equipment-reactivate"),
    path("technical-catalogs/equipment-methods/", MetodoEquipoViewSet.as_view({"get": "list", "post": "create"}), name="equipment-methods-list"),
    path("technical-catalogs/equipment-methods/<int:pk>/", MetodoEquipoViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="equipment-methods-detail"),
    path("technical-catalogs/equipment-methods/<int:pk>/reactivate/", MetodoEquipoViewSet.as_view({"post": "reactivate"}), name="equipment-methods-reactivate"),
    path("technical-catalogs/units/", UnidadViewSet.as_view({"get": "list", "post": "create"}), name="units-list"),
    path("technical-catalogs/units/<int:pk>/", UnidadViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="units-detail"),
    path("technical-catalogs/units/<int:pk>/reactivate/", UnidadViewSet.as_view({"post": "reactivate"}), name="units-reactivate"),
    path("technical-catalogs/conditions/", CondicionViewSet.as_view({"get": "list", "post": "create"}), name="conditions-list"),
    path("technical-catalogs/conditions/<int:pk>/", CondicionViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="conditions-detail"),
    path("technical-catalogs/conditions/<int:pk>/reactivate/", CondicionViewSet.as_view({"post": "reactivate"}), name="conditions-reactivate"),
    path("lubrication/tests/", PruebaViewSet.as_view({"get": "list", "post": "create"}), name="pruebas-list"),
    path("lubrication/tests/<int:pk>/", PruebaViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="prueba-detail"),
    path("misc/tests/", PruebaViewSet.as_view({"get": "list", "post": "create"}), name="tests-list"),
    path("misc/tests/<int:pk>/", PruebaViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="tests-detail"),
    path("misc/tests/<int:pk>/restore/", PruebaViewSet.as_view({"post": "restore"}), name="tests-restore"),
    path("technical-config/limit-fields/", PruebaLimiteCampoViewSet.as_view({"get": "list", "post": "create"}), name="dynamic-limit-fields-list"),
    path("technical-config/limit-fields/<int:pk>/", PruebaLimiteCampoViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="dynamic-limit-fields-detail"),
    path("technical-config/limit-fields/<int:pk>/restore/", PruebaLimiteCampoViewSet.as_view({"post": "restore"}), name="dynamic-limit-fields-restore"),
]
