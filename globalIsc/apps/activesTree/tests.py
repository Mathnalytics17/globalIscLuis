from django.utils import timezone
from rest_framework.test import APITestCase

from apps.activesTree.api.models.index import PuntoMuestreo, AsignacionPuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.misc.api.models.companies.index import Empresa
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.users.api.models.index import User


class SamplingPointApiTests(APITestCase):
    def setUp(self):
        self.company = Empresa.objects.create(nombre='Cliente arbol')
        self.user = User.objects.create_superuser(email='tree@example.com', password='test')
        self.machine = Maquina.objects.create(nombre='Maquina A', empresa=self.company)
        self.other_machine = Maquina.objects.create(nombre='Maquina B', empresa=self.company)
        self.batch = LoteMuestras.objects.create(
            id='L20990001', tipo_cliente='registrado', cliente_empresa=self.company,
            fecha_envio=timezone.localdate(), usuario_registro=self.user,
        )
        self.sample_a = self._sample('M20990001', self.machine)
        self.sample_b = self._sample('M20990002', self.other_machine)
        self.client.force_authenticate(self.user)

    def _sample(self, sample_id, machine):
        return Muestra.objects.create(
            id=sample_id, lote=self.batch, fecha_toma=timezone.now(),
            referencia_equipo=machine, usuario_registro=self.user,
        )

    def test_point_is_created_inside_machine_and_exposed_in_tree(self):
        response = self.client.post('/api/sampling-points/', {
            'maquina': self.machine.id, 'nombre': 'Puerto principal',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['empresa_id'], self.company.id)

    def test_bulk_assignment_skips_samples_from_other_machine(self):
        point = PuntoMuestreo.objects.create(maquina=self.machine, nombre='Puerto 1')
        response = self.client.post(
            f'/api/sampling-points/{point.id}/organize/',
            {'lote_id': self.batch.id}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['resumen'], {'asignadas': 1, 'sin_cambios': 0, 'omitidas': 1})
        self.assertTrue(AsignacionPuntoMuestreo.objects.filter(muestra=self.sample_a, activa=True).exists())
        self.assertFalse(AsignacionPuntoMuestreo.objects.filter(muestra=self.sample_b, activa=True).exists())

    def test_reassignment_closes_previous_history(self):
        first = PuntoMuestreo.objects.create(maquina=self.machine, nombre='Puerto 1')
        second = PuntoMuestreo.objects.create(maquina=self.machine, nombre='Puerto 2')
        self.client.post(f'/api/sampling-points/{first.id}/organize/', {'sample_ids': [self.sample_a.id]}, format='json')
        self.client.post(f'/api/sampling-points/{second.id}/organize/', {'sample_ids': [self.sample_a.id]}, format='json')
        old = AsignacionPuntoMuestreo.objects.get(muestra=self.sample_a, punto_muestreo=first)
        current = AsignacionPuntoMuestreo.objects.get(muestra=self.sample_a, punto_muestreo=second)
        self.assertFalse(old.activa)
        self.assertIsNotNone(old.finalizado_en)
        self.assertTrue(current.activa)

    def test_batch_list_can_be_filtered_from_machine_and_sampling_point(self):
        point = PuntoMuestreo.objects.create(maquina=self.machine, nombre='Puerto filtro')
        AsignacionPuntoMuestreo.objects.create(
            muestra=self.sample_a, punto_muestreo=point, asignado_por=self.user,
        )
        by_machine = self.client.get(f'/api/lubrication/sample-batches/?machine_id={self.machine.id}')
        by_point = self.client.get(f'/api/lubrication/sample-batches/?sampling_point_id={point.id}')
        self.assertEqual(by_machine.status_code, 200)
        self.assertEqual(by_point.status_code, 200)
        machine_row = by_machine.data['results'][0]
        point_row = by_point.data['results'][0]
        self.assertEqual(machine_row['muestras_coincidentes'], 1)
        self.assertEqual(point_row['muestras_coincidentes'], 1)
