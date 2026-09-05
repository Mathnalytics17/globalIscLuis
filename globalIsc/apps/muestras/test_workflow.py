from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.misc.api.models.pruebas.index import Prueba
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.services.workflow import capabilities_for_batch
from apps.users.api.models.index import User


class BatchWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="workflow@example.com",
            password="test-password",
            is_active=True,
            role=User.Role.GLOBAL,
        )
        self.batch = LoteMuestras.objects.create(
            id="LWORK0001",
            fecha_envio=date.today(),
            usuario_registro=self.user,
        )
        self.sample = Muestra.objects.create(
            id="MWORK0001",
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )
        self.test = Prueba.objects.create(nombre_variable="Workflow", acronimo="WORK")

    def capabilities(self):
        self.batch.refresh_from_db()
        return capabilities_for_batch(self.batch).to_dict()

    def test_operations_follow_the_real_batch_progress(self):
        initial = self.capabilities()
        self.assertTrue(initial["ingresar_laboratorio"])
        self.assertFalse(initial["asignar_pruebas"])
        self.assertFalse(initial["ingresar_resultados"])

        self.sample.is_ingresado = True
        self.sample.save(update_fields=["is_ingresado"])
        entered = self.capabilities()
        self.assertTrue(entered["asignar_pruebas"])
        self.assertFalse(entered["ingresar_resultados"])

        assignment = PruebaMuestra.objects.create(
            muestra=self.sample,
            prueba=self.test,
            usuario_solicitud=self.user,
            estado_asignacion="confirmada",
        )
        assigned = self.capabilities()
        self.assertTrue(assigned["ingresar_resultados"])
        self.assertFalse(assigned["revisar_resultados"])

        assignment.completada = True
        assignment.estatus = "completado"
        assignment.save(update_fields=["completada", "estatus"])
        completed = self.capabilities()
        self.assertTrue(completed["ingresar_resultados"])
        self.assertTrue(completed["revisar_resultados"])

        assignment.is_revisada = True
        assignment.estatus = "aprobado"
        assignment.save(update_fields=["is_revisada", "estatus"])
        reviewed = self.capabilities()
        self.assertFalse(reviewed["revisar_resultados"])
        self.assertTrue(reviewed["interpretar_resultados"])

    def test_reported_batch_is_locked(self):
        self.batch.estado = "reportado"
        self.batch.save(update_fields=["estado"])

        self.assertFalse(any(self.capabilities().values()))
