from django.db import transaction
from django.db.models.signals import post_delete, post_save

from apps.activesTree.api.models.index import PuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.misc.api.models.companies.index import Empresa
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.reporte.api.models.index import Reporte, ReporteEnvio
from apps.reporte.report_list_cache import invalidate_report_list


def _invalidate_after_commit(**kwargs):
    transaction.on_commit(invalidate_report_list)


for _model in (Reporte, ReporteEnvio, Muestra, LoteMuestras, Empresa, Maquina, PuntoMuestreo):
    post_save.connect(_invalidate_after_commit, sender=_model, dispatch_uid=f"report_list_cache_save_{_model._meta.label_lower}")
    post_delete.connect(_invalidate_after_commit, sender=_model, dispatch_uid=f"report_list_cache_delete_{_model._meta.label_lower}")
