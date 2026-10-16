from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.misc.api.models.companies.index import Empresa
from apps.activesTree.services import ensure_company_root


@receiver(post_save, sender=Empresa)
def maintain_company_asset_root(sender, instance, **kwargs):
    if instance.is_active:
        ensure_company_root(instance)
