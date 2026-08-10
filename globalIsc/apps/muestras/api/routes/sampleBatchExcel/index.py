from django.urls import path
from apps.muestras.api.views.sampleBatchExcel.index import SampleBatchExcelImportViewSet

urlpatterns = [
    path(
        "lubrication/sample-batches/excel/template/",
        SampleBatchExcelImportViewSet.as_view({"get": "template"}),
        name="sample-batches-excel-template",
    ),
    path(
        "lubrication/sample-batches/excel/preview/",
        SampleBatchExcelImportViewSet.as_view({"post": "preview"}),
        name="sample-batches-excel-preview",
    ),
]
