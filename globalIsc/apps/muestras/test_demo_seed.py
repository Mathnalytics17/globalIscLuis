import os
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.activesTree.api.models.index import PuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.reporte.api.models.index import Reporte
from apps.resultado.api.models.index import Resultado


class DemoEnvironmentSeedTests(TestCase):
    def test_seed_creates_assets_trends_and_operational_scenarios(self):
        with patch.dict(os.environ, {"DEMO_DEFAULT_PASSWORD": "Demo-seed-password-123!"}):
            call_command("seed_demo_environment", months=2)

        self.assertGreaterEqual(Maquina.objects.filter(activo=True).count(), 10)
        self.assertGreaterEqual(PuntoMuestreo.objects.filter(activo=True).count(), 20)
        self.assertTrue(LoteMuestras.objects.filter(id="SHOW-REC-01", estado="recibido").exists())
        self.assertTrue(LoteMuestras.objects.filter(id="SHOW-LAB-01", estado="en_laboratorio").exists())
        self.assertTrue(LoteMuestras.objects.filter(id="SHOW-PAR-01", estado="parcial").exists())
        self.assertTrue(LoteMuestras.objects.filter(id="SHOW-CMP-01", estado="resultados_completos").exists())
        self.assertTrue(LoteMuestras.objects.filter(id="SHOW-RPT-01", estado="reportado").exists())
        self.assertTrue(Reporte.objects.filter(lote_id="SHOW-RPT-01", estatus="aprobado").exists())
        self.assertTrue(Reporte.objects.filter(lote_id="SHOW-RPT-01", estatus="pendiente_aprobacion").exists())

        before = (Maquina.objects.count(), PuntoMuestreo.objects.count(), LoteMuestras.objects.count(), Resultado.objects.count(), Reporte.objects.count())
        with patch.dict(os.environ, {"DEMO_DEFAULT_PASSWORD": "Demo-seed-password-123!"}):
            call_command("seed_demo_environment", months=2)
        self.assertEqual(before, (Maquina.objects.count(), PuntoMuestreo.objects.count(), LoteMuestras.objects.count(), Resultado.objects.count(), Reporte.objects.count()))
