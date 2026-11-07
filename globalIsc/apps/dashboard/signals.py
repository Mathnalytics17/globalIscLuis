"""Keep dashboard cache coherent with its operational source models."""

from django.db import transaction
from django.db.models.signals import post_delete, post_save

from apps.dashboard.operational_cache import invalidate_operational_center
from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.tipoGestionMuestra.index import TipoGestionMuestra
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.reporte.api.models.index import Reporte
from apps.resultado.api.models.index import Resultado


def _invalidate_after_commit(**kwargs):
    transaction.on_commit(invalidate_operational_center)


for _model in (Empresa, TipoGestionMuestra, LoteMuestras, Muestra, PruebaMuestra, Reporte, Resultado):
    post_save.connect(_invalidate_after_commit, sender=_model, dispatch_uid=f"dashboard_cache_save_{_model._meta.label_lower}")
    post_delete.connect(_invalidate_after_commit, sender=_model, dispatch_uid=f"dashboard_cache_delete_{_model._meta.label_lower}")
