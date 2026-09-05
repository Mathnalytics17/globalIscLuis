from django.urls import path

from .views.index import ReporteViewSet


urlpatterns = [
    path("lubrication/reports/dashboard/", ReporteViewSet.as_view({"get": "dashboard"}), name="reportes-dashboard"),
    path("lubrication/reports/generate-from-interpretation/", ReporteViewSet.as_view({"post": "generate_from_interpretation"}), name="reportes-generate-from-interpretation"),
    path("lubrication/reports/generate-batch-from-interpretation/", ReporteViewSet.as_view({"post": "generate_batch_from_interpretation"}), name="reportes-generate-batch-from-interpretation"),
    path("lubrication/reports/preview-from-interpretation/", ReporteViewSet.as_view({"get": "preview_from_interpretation"}), name="reportes-preview-from-interpretation"),
    path("lubrication/reports/upload-signature/", ReporteViewSet.as_view({"post": "upload_signature"}), name="reportes-upload-signature"),
    path("lubrication/reports/imprimir_reporte/", ReporteViewSet.as_view({"get": "imprimir_reporte"}), name="imprimir-reporte"),
    path("lubrication/reports/batch-export/", ReporteViewSet.as_view({"get": "export_batch"}), name="reportes-batch-export"),
    path("lubrication/reports/batch-send/", ReporteViewSet.as_view({"post": "send_batch_email"}), name="reportes-batch-send"),
    path("lubrication/reports/", ReporteViewSet.as_view({"get": "list", "post": "create"}), name="reportes-list"),
    path("lubrication/reports/<int:pk>/send-email/", ReporteViewSet.as_view({"post": "send_email_report"}), name="reporte-send-email"),
    path("lubrication/reports/<int:pk>/publish-client/", ReporteViewSet.as_view({"post": "publish_client"}), name="reporte-publish-client"),
    path("lubrication/reports/<int:pk>/unpublish-client/", ReporteViewSet.as_view({"post": "unpublish_client"}), name="reporte-unpublish-client"),
    path("lubrication/reports/<int:pk>/versions/", ReporteViewSet.as_view({"get": "versions"}), name="reporte-versions"),
    path("lubrication/reports/<int:pk>/approve/", ReporteViewSet.as_view({"post": "aprobar"}), name="reporte-aprobar"),
    path("lubrication/reports/<int:pk>/aprobar/", ReporteViewSet.as_view({"post": "aprobar"}), name="reporte-aprobar-alias"),
    path("lubrication/reports/<int:pk>/send-approval/", ReporteViewSet.as_view({"post": "enviar_aprobacion"}), name="reporte-enviar-aprobacion"),
    path("lubrication/reports/<int:pk>/annul/", ReporteViewSet.as_view({"post": "annul"}), name="reporte-annul"),
    path("lubrication/reports/<int:pk>/", ReporteViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="reporte-detail"),
    path("upload/signature/", ReporteViewSet.as_view({"post": "upload_signature"}), name="upload-signature"),
]
