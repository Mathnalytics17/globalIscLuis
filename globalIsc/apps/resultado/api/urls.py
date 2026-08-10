from django.urls import path

from .views.index import ResultadoViewSet


urlpatterns = [
    path("lubrication/results/", ResultadoViewSet.as_view({"get": "list", "post": "create"}), name="resultado-list"),
    path("lubrication/results/<int:pk>/", ResultadoViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="resultado-detail"),
    path("lubrication/results/<int:pk>/revisar/", ResultadoViewSet.as_view({"post": "revisar"}), name="resultado-revisar"),
    path("lubrication/result-entry/batches/", ResultadoViewSet.as_view({"get": "entry_batches"}), name="result-entry-batches"),
    path("lubrication/result-entry/batches/<str:lote_id>/confirm-all/", ResultadoViewSet.as_view({"post": "confirm_batch_results"}), name="result-entry-confirm-batch-results"),
    path("lubrication/result-entry/batches/<str:lote_id>/", ResultadoViewSet.as_view({"get": "entry_batch_detail"}), name="result-entry-batch-detail"),
    path("lubrication/result-entry/sample-tests/<int:prueba_muestra_id>/form/", ResultadoViewSet.as_view({"get": "entry_form"}), name="result-entry-form"),
    path("lubrication/result-entry/sample-tests/<int:prueba_muestra_id>/save-draft/", ResultadoViewSet.as_view({"post": "save_draft"}), name="result-entry-save-draft"),
    path("lubrication/result-entry/sample-tests/<int:prueba_muestra_id>/confirm/", ResultadoViewSet.as_view({"post": "confirm_result"}), name="result-entry-confirm"),
    path("lubrication/result-entry/excel/template/", ResultadoViewSet.as_view({"get": "excel_template"}), name="result-entry-excel-template"),
    path("lubrication/result-entry/excel/export/", ResultadoViewSet.as_view({"get": "excel_export"}), name="result-entry-excel-export"),
    path("lubrication/result-entry/excel/preview/", ResultadoViewSet.as_view({"post": "excel_preview"}), name="result-entry-excel-preview"),
    path("lubrication/result-entry/excel/import/", ResultadoViewSet.as_view({"post": "excel_import"}), name="result-entry-excel-import"),
    path("lubrication/review-results/batches/", ResultadoViewSet.as_view({"get": "review_batches"}), name="review-results-batches"),
    path("lubrication/review-results/batches/<str:lote_id>/complete/", ResultadoViewSet.as_view({"post": "complete_batch_review"}), name="review-results-complete-batch"),
    path("lubrication/review-results/batches/<str:lote_id>/", ResultadoViewSet.as_view({"get": "review_batch_detail"}), name="review-results-batch-detail"),
    path("lubrication/review-results/results/<int:resultado_id>/history/", ResultadoViewSet.as_view({"get": "result_history"}), name="review-results-history"),
    path("lubrication/review-results/results/<int:resultado_id>/correct/", ResultadoViewSet.as_view({"post": "correct_result"}), name="review-results-correct"),
    path("lubrication/review-results/sample-tests/<int:prueba_muestra_id>/mark-reviewed/", ResultadoViewSet.as_view({"post": "mark_sample_test_reviewed"}), name="review-results-mark-reviewed"),
    path("lubrication/interpretation/batches/<str:lote_id>/", ResultadoViewSet.as_view({"get": "interpretation_batch_detail"}), name="interpretation-batch-detail"),
    path("lubrication/interpretation/samples/<str:muestra_id>/trends/", ResultadoViewSet.as_view({"get": "interpretation_trends"}), name="interpretation-trends"),
    path("lubrication/interpretation/samples/<str:muestra_id>/", ResultadoViewSet.as_view({"get": "interpretation_sample", "patch": "save_interpretation_sample", "post": "save_interpretation_sample"}), name="interpretation-sample"),
]
