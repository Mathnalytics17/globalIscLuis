from django.utils import timezone
from rest_framework.test import APITestCase

from apps.activesTree.api.models.index import Carpeta, PuntoMuestreo, AsignacionPuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.activesTree.services import ensure_machine_tree_node
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

    def test_company_root_is_created_automatically(self):
        self.assertTrue(Carpeta.objects.filter(
            compania=self.company, typeFolder='root', id_parent_node='-1',
        ).exists())

    def test_company_rename_updates_its_root_label(self):
        response = self.client.patch(
            f'/api/companies/{self.company.id}/',
            {'nombre': 'Mineros Aluvial S.A.S.'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        root = Carpeta.objects.get(compania=self.company, typeFolder='root', id_parent_node='-1')
        self.assertEqual(root.nombre, 'Mineros Aluvial S.A.S.')

    def test_company_root_cannot_be_renamed_as_a_folder(self):
        root = Carpeta.objects.get(compania=self.company, typeFolder='root', id_parent_node='-1')

        response = self.client.patch(
            f'/api/folders/{root.id}/',
            {'nombre': 'Nombre incorrecto'},
            format='json',
        )

        self.assertEqual(response.status_code, 409)
        root.refresh_from_db()
        self.assertEqual(root.nombre, self.company.nombre)

    def test_machine_name_can_repeat_in_another_company(self):
        other_company = Empresa.objects.create(nombre='Cliente B')
        response = self.client.post('/api/machines/', {
            'empresa': other_company.id,
            'nombre': self.machine.nombre,
        }, format='json')

        self.assertEqual(response.status_code, 201, response.data)
        other_machine = Maquina.objects.get(pk=response.data['id'])
        self.assertEqual(other_machine.nombre, self.machine.nombre)
        self.assertNotEqual(other_machine.empresa_id, self.machine.empresa_id)
        self.assertTrue(Carpeta.objects.filter(machine=other_machine).exists())

    def test_machine_is_created_in_selected_folder(self):
        root = Carpeta.objects.get(compania=self.company, typeFolder='root', id_parent_node='-1')
        drags = Carpeta.objects.create(
            compania=self.company,
            nombre='Dragas',
            typeFolder='folder',
            id_parent_node=str(root.id),
        )

        response = self.client.post('/api/machines/', {
            'empresa': self.company.id,
            'nombre': 'Draga creada en carpeta',
            'parent_folder': drags.id,
        }, format='json')

        self.assertEqual(response.status_code, 201, response.data)
        node = Carpeta.objects.get(machine_id=response.data['id'])
        self.assertEqual(node.id_parent_node, str(drags.id))
        self.assertEqual(Carpeta.objects.filter(machine_id=response.data['id']).count(), 1)
    def test_inactive_machine_node_is_hidden_and_can_be_removed(self):
        node = ensure_machine_tree_node(self.machine)
        self.machine.activo = False
        self.machine.save(update_fields=['activo'])

        tree = self.client.get('/api/actives-tree/basic-structure/')
        self.assertEqual(tree.status_code, 200)
        self.assertNotIn(str(self.machine.id), str(tree.data['structure']))

        deleted = self.client.delete(f'/api/folders/{node.id}/')
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(Carpeta.objects.filter(pk=node.id).exists())
        self.assertTrue(Maquina.objects.filter(pk=self.machine.id, activo=False).exists())

    def test_tree_always_exposes_company_name_for_legacy_root(self):
        root = Carpeta.objects.get(compania=self.company, typeFolder='root', id_parent_node='-1')
        # Simulates roots that were renamed through the legacy UI.
        Carpeta.objects.filter(pk=root.pk).update(nombre='Etiqueta antigua')

        response = self.client.get('/api/actives-tree/basic-structure/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['structure'][0]['nombre'], self.company.nombre)
        root.refresh_from_db()
        self.assertEqual(root.nombre, self.company.nombre)

    def test_global_lubricant_can_be_used_by_a_point_from_any_company(self):
        created = self.client.post('/api/lubricants/', {
            'fabricante': 'Petrobras', 'referencia': 'Hydra 68',
        }, format='json')
        self.assertEqual(created.status_code, 201)

        other_company = Empresa.objects.create(nombre='Otro cliente')
        other_machine = Maquina.objects.create(nombre='Maquina externa', empresa=other_company)
        point = self.client.post('/api/sampling-points/', {
            'maquina': other_machine.id,
            'nombre': 'Punto externo',
            'lubricante_catalogo': created.data['id'],
        }, format='json')
        self.assertEqual(point.status_code, 201)
        self.assertEqual(point.data['lubricante_catalogo'], created.data['id'])

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

    def test_changing_sample_machine_closes_point_from_previous_machine(self):
        point = PuntoMuestreo.objects.create(maquina=self.machine, nombre='Punto de la máquina A')
        AsignacionPuntoMuestreo.objects.create(
            muestra=self.sample_a, punto_muestreo=point, asignado_por=self.user,
        )

        response = self.client.patch(
            f'/api/lubrication/samples/{self.sample_a.id}/',
            {'referencia_equipo': self.other_machine.id},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        assignment = AsignacionPuntoMuestreo.objects.get(muestra=self.sample_a, punto_muestreo=point)
        self.assertFalse(assignment.activa)
        self.assertIsNotNone(assignment.finalizado_en)

    def test_sample_cannot_select_point_from_a_different_machine(self):
        foreign_point = PuntoMuestreo.objects.create(maquina=self.other_machine, nombre='Punto de la máquina B')

        response = self.client.put(
            f'/api/lubrication/samples/{self.sample_a.id}/measurement-point/',
            {'punto_muestreo_id': foreign_point.id},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(AsignacionPuntoMuestreo.objects.filter(muestra=self.sample_a, activa=True).exists())

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
