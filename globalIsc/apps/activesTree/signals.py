from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.misc.api.models.companies.index import Empresa
from apps.activesTree.api.models.index import Carpeta, PuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.activesTree.machine_list_cache import invalidate_machine_list_cache
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.resultado.api.models.index import Resultado
from apps.activesTree.services import ensure_company_root


@receiver(post_save, sender=Empresa)
def maintain_company_asset_root(sender, instance, **kwargs):
    if instance.is_active:
        ensure_company_root(instance)


def _invalidate_machine_list_after_commit(**kwargs):
    """Only discard cached lists after the database write is durable."""
    transaction.on_commit(invalidate_machine_list_cache)


for _model in (Empresa, Maquina, PuntoMuestreo, Carpeta, Muestra, PruebaMuestra, Resultado):
    post_save.connect(_invalidate_machine_list_after_commit, sender=_model)
    post_delete.connect(_invalidate_machine_list_after_commit, sender=_model)
