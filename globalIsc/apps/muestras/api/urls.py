from django.urls import include, path

from .views.ingresoLabLote.index import IngresoLabLoteViewSet
from .views.loteMuestras.index import LoteMuestrasViewSet
from .views.pruebaMuestra.index import PruebaMuestraViewSet
from .views.sampleBatchExcel.index import SampleBatchExcelImportViewSet


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
    path("lubrication/sample-batches/<str:pk>/recalcular-estado/", LoteMuestrasViewSet.as_view({"post": "recalcular_estado"}), name="sample-batches-recalculate-status"),
    path("lubrication/sample-batches/<str:pk>/samples/", LoteMuestrasViewSet.as_view({"post": "add_samples"}), name="sample-batches-add-samples"),
    path("lubrication/sample-batches/<str:pk>/cancel/", LoteMuestrasViewSet.as_view({"post": "cancel"}), name="sample-batches-cancel"),
    path("lubrication/sample-batches/<str:pk>/reopen/", LoteMuestrasViewSet.as_view({"post": "reopen"}), name="sample-batches-reopen"),
    path("lubrication/sample-batches/<str:pk>/", LoteMuestrasViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="sample-batches-detail"),
]
