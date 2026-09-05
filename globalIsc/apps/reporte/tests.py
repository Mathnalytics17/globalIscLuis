import io
import zipfile
from unittest.mock import patch
from pypdf import PdfReader, PdfWriter

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate

from apps.misc.api.models.companies.index import Empresa
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.reporte.api.models.index import Reporte
from apps.reporte.api.views.index import (
    ReporteViewSet,
    _clean_limit_label,
    _report_limit_bands,
    _report_status,
)
from apps.users.api.models.index import User


class ReportSemaphoreTests(SimpleTestCase):
    def test_report_approval_routes_are_registered(self):
        canonical = reverse("reporte-aprobar", kwargs={"pk": 15})
        cached_client_alias = reverse("reporte-aprobar-alias", kwargs={"pk": 15})

        self.assertEqual(canonical, "/api/lubrication/reports/15/approve/")
        self.assertEqual(cached_client_alias, "/api/lubrication/reports/15/aprobar/")
        self.assertEqual(resolve(canonical).url_name, "reporte-aprobar")
        self.assertEqual(resolve(cached_client_alias).url_name, "reporte-aprobar-alias")

    def test_semaphore_statuses_remain_distinct(self):
        self.assertEqual(_report_status("CRITICO"), "CRÍTICO")
        self.assertEqual(_report_status("NO_DESEADO"), "ALERTA")
        self.assertEqual(_report_status("NORMAL"), "ACEPTABLE")

    def test_limit_bands_format_structured_rule_without_raw_dict(self):
        bands = _report_limit_bands({
            "operator": "between",
            "unit": "cSt",
            "limit_value": {
                "min_critico": 12,
                "min_aceptable": 22,
                "max_aceptable": 25,
                "max_critico": 33,
                "usar_amarillo": True,
            },
        })

        self.assertEqual(bands["acceptable"], "Entre 22 cSt y 25 cSt")
        self.assertEqual(
            bands["warning"],
            "Desde 12 cSt hasta antes de 22 cSt; o Más de 25 cSt y hasta 33 cSt",
        )
        self.assertEqual(bands["critical"], "Menor que 12 cSt; o Mayor que 33 cSt")
        self.assertNotIn("{", " ".join(bands.values()))

    def test_empty_warning_gap_is_not_rendered(self):
        bands = _report_limit_bands({
            "operator": "max",
            "limit_value": {
                "max_aceptable": 0,
                "max_critico": 0,
                "usar_amarillo": True,
            },
        })

        self.assertEqual(bands["acceptable"], "Hasta 0")
        self.assertEqual(bands["warning"], "")
        self.assertEqual(bands["critical"], "Mayor que 0")

    def test_legacy_dict_limit_is_never_printed(self):
        self.assertEqual(
            _clean_limit_label("{'min_aceptable': 10, 'max_aceptable': 20}"),
            "Límite configurado",
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ReportEmailTests(TestCase):
    def setUp(self):
        self.company = Empresa.objects.create(nombre="Cliente reporte", email="cliente@example.com")
        self.user = User.objects.create_user(
            email="report-owner@example.com",
            password="test-password",
            empresa=self.company,
        )
        self.batch = LoteMuestras.objects.create(
            id="L20269999",
            cliente_empresa=self.company,
            contacto_email="destino@example.com",
            fecha_envio=timezone.localdate(),
            usuario_registro=self.user,
        )
        self.sample = Muestra.objects.create(
            id="M20269999",
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )
        self.report = Reporte.objects.create(
            consecutivo="R20269999",
            muestra=self.sample,
            lote=self.batch,
            version=1,
            fecha_emision=timezone.now(),
            usuario_emision=self.user,
        )

    @patch.object(ReporteViewSet, "_render_report_html", return_value="<html></html>")
    @patch.object(ReporteViewSet, "_generar_pdf", return_value={"pdf": b"%PDF-test"})
    def test_email_contains_download_link_and_pdf_attachment(self, _pdf, _html):
        self._approve(self.report)
        factory = APIRequestFactory()
        raw_request = factory.post("/api/lubrication/reports/1/send-email/", {}, format="json")
        raw_request.user = self.user

        view = ReporteViewSet()
        view.action_map = {"post": "send_email_report"}
        request = view.initialize_request(raw_request)
        request.user = self.user
        view.request = request
        view.action = "send_email_report"
        view.format_kwarg = None
        view.kwargs = {"pk": self.report.pk}
        view.get_object = lambda: self.report

        response = view.send_email_report(request, pk=self.report.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("imprimir_reporte/?pdf=", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].attachments[0][2], "application/pdf")

    def test_unapproved_report_cannot_be_sent_to_client(self):
        factory = APIRequestFactory()
        raw_request = factory.post("/api/lubrication/reports/1/send-email/", {}, format="json")
        raw_request.user = self.user
        view = ReporteViewSet()
        view.action_map = {"post": "send_email_report"}
        request = view.initialize_request(raw_request)
        request.user = self.user
        view.request = request
        view.action = "send_email_report"
        view.format_kwarg = None
        view.kwargs = {"pk": self.report.pk}
        view.get_object = lambda: self.report

        response = view.send_email_report(request, pk=self.report.pk)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(mail.outbox)

    def test_generate_uses_account_default_signature(self):
        self.user.is_superuser = True
        self.user.is_active = True
        self.user.firma_predeterminada.name = "firmas_usuarios/firma-admin.png"
        self.user.save(update_fields=["is_superuser", "is_active", "firma_predeterminada"])
        self.sample.is_revisado = True
        self.sample.campos_adicionales = {
            "interpretacion": {"conclusion": "Muestra evaluada."},
        }
        self.sample.save(update_fields=["is_revisado", "campos_adicionales"])

        factory = APIRequestFactory()
        request = factory.post(
            "/api/lubrication/reports/generate-from-interpretation/",
            {"muestra": self.sample.id},
            format="json",
        )
        force_authenticate(request, user=self.user)
        view = ReporteViewSet.as_view({"post": "generate_from_interpretation"})

        response = view(request)

        self.assertEqual(response.status_code, 201)
        generated = Reporte.objects.get(pk=response.data["id"])
        self.assertEqual(generated.firma_ruta, "firmas_usuarios/firma-admin.png")

    def test_generate_batch_from_interpretation_creates_one_report_per_sample(self):
        self.user.is_superuser = True
        self.user.is_active = True
        self.user.save(update_fields=["is_superuser", "is_active"])
        self.sample.is_revisado = True
        self.sample.campos_adicionales = {"interpretacion": {"conclusion": "Muestra evaluada."}}
        self.sample.save(update_fields=["is_revisado", "campos_adicionales"])

        factory = APIRequestFactory()
        request = factory.post(
            "/api/lubrication/reports/generate-batch-from-interpretation/",
            {"lote": self.batch.id, "responsable": "Responsable del lote"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        view = ReporteViewSet.as_view({"post": "generate_batch_from_interpretation"})

        response = view(request)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["generated"], 1)
        self.assertTrue(Reporte.objects.filter(muestra=self.sample, Responsable="Responsable del lote").exists())

    def test_dashboard_uses_lightweight_report_read_model(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self.report.snapshot = {"resultados": ["large-payload"] * 100}
        self.report.save(update_fields=["snapshot"])

        factory = APIRequestFactory()
        request = factory.get(
            "/api/lubrication/reports/dashboard/",
            {"lote": self.batch.id},
        )
        force_authenticate(request, user=self.user)
        view = ReporteViewSet.as_view({"get": "dashboard"})

        with self.assertNumQueries(2):
            response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["total"], 1)
        self.assertNotIn("snapshot", response.data["results"][0])
        self.assertEqual(response.data["results"][0]["ultima_version"], 1)

    def _approve(self, report):
        report.usuario_aprobacion = self.user
        report.fecha_aprobacion = timezone.now()
        report.estatus = "aprobado"
        report.save(update_fields=["usuario_aprobacion", "fecha_aprobacion", "estatus"])

    def _batch_request(self, format="zip"):
        factory = APIRequestFactory()
        request = factory.get(
            "/api/lubrication/reports/batch-export/",
            {"lote": self.batch.id, "formato": format},
        )
        force_authenticate(request, user=self.user)
        return ReporteViewSet.as_view({"get": "export_batch"})(request)

    def test_batch_export_requires_approved_report_for_every_sample(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self._approve(self.report)
        Muestra.objects.create(
            id="M20269998",
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )

        response = self._batch_request()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["muestras_sin_reporte_aprobado"], ["M20269998"])

    @patch.object(ReporteViewSet, "_pdf_bytes_for_report", return_value=b"%PDF-individual")
    def test_batch_zip_uses_latest_approved_version_and_keeps_individual_files(self, _pdf):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self._approve(self.report)
        Reporte.objects.create(
            consecutivo="R20269998",
            muestra=self.sample,
            lote=self.batch,
            version=2,
            fecha_emision=timezone.now(),
            usuario_emision=self.user,
            estatus="generado",
        )
        second_sample = Muestra.objects.create(
            id="M20269998",
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )
        second_report = Reporte.objects.create(
            consecutivo="R20269997",
            muestra=second_sample,
            lote=self.batch,
            version=1,
            fecha_emision=timezone.now(),
            usuario_emision=self.user,
        )
        self._approve(second_report)

        response = self._batch_request()

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = archive.namelist()
        self.assertEqual(len(names), 2)
        self.assertTrue(any("M20269999_R20269999_v1.pdf" in name for name in names))
        self.assertFalse(any("R20269998" in name for name in names))

    def test_consolidated_pdf_appends_one_approved_sample_report_after_another(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self._approve(self.report)
        second_sample = Muestra.objects.create(
            id="M20269998",
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )
        second_report = Reporte.objects.create(
            consecutivo="R20269997",
            muestra=second_sample,
            lote=self.batch,
            version=1,
            fecha_emision=timezone.now(),
            usuario_emision=self.user,
        )
        self._approve(second_report)
        single_page = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=400)
        writer.write(single_page)

        with patch.object(ReporteViewSet, "_pdf_bytes_for_report", return_value=single_page.getvalue()):
            response = self._batch_request(format="pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(PdfReader(io.BytesIO(response.content)).pages), 2)

    @patch.object(ReporteViewSet, "_batch_file", return_value=(b"zip-content", "reportes_L20269999.zip", "application/zip"))
    def test_batch_email_sends_one_attachment_and_marks_every_approved_report(self, _batch_file):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self._approve(self.report)
        second_sample = Muestra.objects.create(
            id="M20269998",
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )
        second_report = Reporte.objects.create(
            consecutivo="R20269997",
            muestra=second_sample,
            lote=self.batch,
            version=1,
            fecha_emision=timezone.now(),
            usuario_emision=self.user,
        )
        self._approve(second_report)
        factory = APIRequestFactory()
        request = factory.post(
            "/api/lubrication/reports/batch-send/",
            {"lote": self.batch.id, "formato": "zip"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = ReporteViewSet.as_view({"post": "send_batch_email"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].attachments[0][2], "application/zip")
        self.report.refresh_from_db()
        second_report.refresh_from_db()
        self.assertEqual(self.report.estatus, "enviado")
        self.assertEqual(second_report.estatus, "enviado")
