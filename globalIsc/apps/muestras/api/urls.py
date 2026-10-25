from django.urls import include, path

from .views.ingresoLabLote.index import IngresoLabLoteViewSet
from .views.loteMuestras.index import LoteMuestrasViewSet
from .views.pruebaMuestra.index import PruebaMuestraViewSet
from .views.sampleBatchExcel.index import SampleBatchExcelImportViewSet
from .views.trazabilidad.index import TrazabilidadViewSet
from .views.trazabilidad.importaciones import CorridaImportacionViewSet


urlpatterns = [
    path("", include("apps.muestras.api.urls_samples")),
    path("lubrication/sample-tests/", PruebaMuestraViewSet.as_view({"get": "list", "post": "create"}), name="pruebas-muestra-list"),
    path("lubrication/sample-tests/assign-batch/", PruebaMuestraViewSet.as_view({"post": "assign_batch"}), name="pruebas-muestra-assign-batch"),
    path("lubrication/sample-tests/by-sample/<str:muestra_id>/", PruebaMuestraViewSet.as_view({"get": "by_sample"}), name="pruebas-muestra-by-sample"),
    path("lubrication/sample-tests/by-batch/<str:lote_id>/", PruebaMuestraViewSet.as_view({"get": "by_batch"}), name="pruebas-muestra-by-batch"),
    path("lubrication/sample-tests/<str:pk>/", PruebaMuestraViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="prueba-muestra-detail"),
    path("lubrication/sample-batches/excel/template/", SampleBatchExcelImportViewSet.as_view({"get": "template"}), name="sample-batches-excel-template"),
    path("lubrication/sample-batches/excel/preview/", SampleBatchExcelImportViewSet.as_view({"post": "preview"}), name="sample-batches-excel-preview"),
    path("lubrication/lab-batch-entries/", IngresoLabLoteViewSet.as_view({"get": "list", "post": "create"}), name="lab-batch-entries-list"),
    path("lubrication/lab-batch-entries/available-batches/", IngresoLabLoteViewSet.as_view({"get": "available_batches"}), name="lab-batch-entries-available-batches"),
    path("lubrication/lab-batch-entries/<int:pk>/", IngresoLabLoteViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="lab-batch-entries-detail"),
    path("lubrication/sample-batches/", LoteMuestrasViewSet.as_view({"get": "list", "post": "create"}), name="sample-batches-list"),
    path("lubrication/sample-batches/resumen/", LoteMuestrasViewSet.as_view({"get": "resumen"}), name="sample-batches-resumen"),
    path("lubrication/traceability/", TrazabilidadViewSet.as_view({"get": "list"}), name="traceability-list"),
    path("lubrication/traceability/summary/", TrazabilidadViewSet.as_view({"get": "summary"}), name="traceability-summary"),
    path("lubrication/traceability/filters/", TrazabilidadViewSet.as_view({"get": "filters"}), name="traceability-filters"),
    path("lubrication/import-runs/", CorridaImportacionViewSet.as_view({"get": "list"}), name="import-runs-list"),
    path("lubrication/import-runs/<int:pk>/", CorridaImportacionViewSet.as_view({"get": "retrieve"}), name="import-runs-detail"),
    path("lubrication/sample-batches/<str:pk>/recalcular-estado/", LoteMuestrasViewSet.as_view({"post": "recalcular_estado"}), name="sample-batches-recalculate-status"),
    # The nested resource serves both the paginated sample workspace (GET)
    # and the established append-samples operation (POST).
    path("lubrication/sample-batches/<str:pk>/samples/", LoteMuestrasViewSet.as_view({"get": "samples", "post": "samples"}), name="sample-batches-samples"),
    path("lubrication/sample-batches/<str:pk>/cancel/", LoteMuestrasViewSet.as_view({"post": "cancel"}), name="sample-batches-cancel"),
    path("lubrication/sample-batches/<str:pk>/reopen/", LoteMuestrasViewSet.as_view({"post": "reopen"}), name="sample-batches-reopen"),
    path("lubrication/sample-batches/<str:pk>/register/", LoteMuestrasViewSet.as_view({"post": "register_draft"}), name="sample-batches-register"),
    path("lubrication/sample-batches/<str:pk>/timeline/", LoteMuestrasViewSet.as_view({"get": "timeline"}), name="sample-batches-timeline"),
    path("lubrication/sample-batches/<str:pk>/", LoteMuestrasViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="sample-batches-detail"),
]
