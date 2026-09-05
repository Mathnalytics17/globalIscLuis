import json
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.models.technicalCatalogs.index import Condicion, Unidad
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.services.assignment_sync import synchronize_batch_assignments
from apps.resultado.api.models.index import Resultado
from apps.users.api.models.index import User


class AssignmentSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="sync@example.com",
            password="test-password",
            is_active=True,
            role=User.Role.GLOBAL,
        )
        self.batch = LoteMuestras.objects.create(
            id="LTEST0001",
            fecha_envio=date.today(),
            usuario_registro=self.user,
        )
        self.sample = Muestra.objects.create(
            id="MTEST0001",
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )
        self.second_sample = Muestra.objects.create(
            id="MTEST0002",
            lote=self.batch,
            fecha_toma=timezone.now(),
            usuario_registro=self.user,
        )
        self.first_test = Prueba.objects.create(nombre_variable="First", acronimo="FIRST")
        self.second_test = Prueba.objects.create(nombre_variable="Second", acronimo="SECOND")
        unit = Unidad.objects.create(nombre="Celsius", simbolo="C", magnitud="temperatura")
        self.condition = Condicion.objects.create(
            nombre="Temperatura 40",
            magnitud="temperatura",
            valor=40,
            unidad=unit,
        )

    def item(self, test, condition=None):
        return {
            "prueba": test,
            "condicion": condition,
            "condicion_texto": str(condition) if condition else None,
            "unidad": None,
        }

    def sync(self, tests):
        return synchronize_batch_assignments(
            lote=self.batch,
            muestras=[self.sample],
            pruebas=tests,
            estado_asignacion="confirmada",
            lote_predefinido=None,
            user=self.user,
        )

    def test_repeated_request_is_idempotent(self):
        first = self.sync([self.item(self.first_test)])
        second = self.sync([self.item(self.first_test)])

        self.assertEqual(first.created, 1)
        self.assertEqual(second.created, 0)
        self.assertEqual(second.updated, 0)
        self.assertEqual(second.unchanged, 1)
        self.assertEqual(PruebaMuestra.objects.count(), 1)

    def test_absent_unprotected_assignment_is_removed(self):
        self.sync([self.item(self.first_test), self.item(self.second_test)])
        result = self.sync([self.item(self.first_test)])

        self.assertEqual(result.deleted, 1)
        self.assertEqual(
            list(PruebaMuestra.objects.values_list("prueba_id", flat=True)),
            [self.first_test.id],
        )

    def test_assignment_with_result_is_protected_from_removal(self):
        self.sync([self.item(self.first_test), self.item(self.second_test)])
        protected = PruebaMuestra.objects.get(prueba=self.second_test)
        Resultado.objects.create(
            prueba_muestra=protected,
            resultado="10",
            fecha_medicion=timezone.now(),
            usuario_medicion=self.user,
        )

        result = self.sync([self.item(self.first_test)])

        self.assertEqual(result.deleted, 0)
        self.assertEqual(result.protected, [protected.id])
        self.assertTrue(PruebaMuestra.objects.filter(pk=protected.pk).exists())

    def test_condition_relation_is_persisted_and_updated(self):
        self.sync([self.item(self.first_test, self.condition)])
        assignment = PruebaMuestra.objects.get(prueba=self.first_test)
        self.assertEqual(assignment.condicion_catalogo, self.condition)

        self.sync([self.item(self.first_test)])
        assignment.refresh_from_db()
        self.assertIsNone(assignment.condicion_catalogo)

    def test_contextual_semaphore_rule_is_persisted_and_updated_intact(self):
        first_rule = json.dumps({
            "resultado_principal_valor": {
                "usar_amarillo": True,
                "min_critico": "100",
                "min_aceptable": "200",
            }
        })
        second_rule = json.dumps({
            "resultado_principal_valor": {
                "usar_amarillo": False,
                "min_aceptable": "250",
            }
        })
        item = self.item(self.first_test)
        item["criterio_limite_valor"] = first_rule

        self.sync([item])
        assignment = PruebaMuestra.objects.get(prueba=self.first_test)
        self.assertEqual(json.loads(assignment.criterio_limite_valor), json.loads(first_rule))

        item["criterio_limite_valor"] = second_rule
        self.sync([item])
        assignment.refresh_from_db()
        self.assertEqual(json.loads(assignment.criterio_limite_valor), json.loads(second_rule))

    def test_syncing_selected_sample_does_not_modify_other_sample(self):
        synchronize_batch_assignments(
            lote=self.batch,
            muestras=[self.second_sample],
            pruebas=[self.item(self.second_test)],
            estado_asignacion="confirmada",
            lote_predefinido=None,
            user=self.user,
        )

        self.sync([self.item(self.first_test)])

        self.assertEqual(
            list(
                PruebaMuestra.objects.filter(muestra=self.sample)
                .values_list("prueba_id", flat=True)
            ),
            [self.first_test.id],
        )
        self.assertEqual(
            list(
                PruebaMuestra.objects.filter(muestra=self.second_sample)
                .values_list("prueba_id", flat=True)
            ),
            [self.second_test.id],
        )
