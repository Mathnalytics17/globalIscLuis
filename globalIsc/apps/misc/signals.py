"""Invalidate catalog responses only after catalog writes are durable."""

from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save

from apps.misc.catalog_cache import invalidate_catalog_cache
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CampoTecnicoMuestra, CatalogoTecnico, CatalogoTecnicoCampo,
    CatalogoTecnicoItem, CatalogoTecnicoItemValor, CatalogoTecnicoVersion,
    CriterioCatalogoSeleccion, CriterioEvaluacionLimite, EscalaComparacion,
    EscalaComparacionItem, PruebaFuenteCatalogo, PruebaFuenteLimite,
    PruebaLimiteCampo,
)
from apps.misc.api.models.lotesPruebasPredefinidos.index import (
    LotePruebasPredefinido, LotePruebasPredefinidoDetalle,
)
from apps.misc.api.models.pruebas.index import (
    Prueba, PruebaResultado, PruebaResultadoComponente,
    PruebaResultadoDisposicion, PruebaResultadoDisposicionItem,
    PruebaResultadoDivision, PruebaResultadoSeparador,
)
from apps.misc.api.models.technicalCatalogs.index import (
    CategoriaUnidad, Condicion, EquipoPrueba, MetodoEquipo, Unidad,
)
from apps.misc.api.models.tipoGestionMuestra.index import TipoGestionMuestra


def _invalidate_after_commit(**kwargs):
    transaction.on_commit(invalidate_catalog_cache)


CATALOG_MODELS = (
    CampoTecnicoMuestra, CatalogoTecnico, CatalogoTecnicoCampo,
    CatalogoTecnicoItem, CatalogoTecnicoItemValor, CatalogoTecnicoVersion,
    CriterioCatalogoSeleccion, CriterioEvaluacionLimite, EscalaComparacion,
    EscalaComparacionItem, PruebaFuenteCatalogo, PruebaFuenteLimite,
    PruebaLimiteCampo, LotePruebasPredefinido, LotePruebasPredefinidoDetalle,
    Prueba, PruebaResultado, PruebaResultadoComponente,
    PruebaResultadoDisposicion, PruebaResultadoDisposicionItem,
    PruebaResultadoDivision, PruebaResultadoSeparador, CategoriaUnidad,
    Condicion, EquipoPrueba, MetodoEquipo, Unidad, TipoGestionMuestra,
)

for _model in CATALOG_MODELS:
    post_save.connect(_invalidate_after_commit, sender=_model, dispatch_uid=f"misc_catalog_save_{_model._meta.label_lower}")
    post_delete.connect(_invalidate_after_commit, sender=_model, dispatch_uid=f"misc_catalog_delete_{_model._meta.label_lower}")

m2m_changed.connect(
    _invalidate_after_commit,
    sender=TipoGestionMuestra.empresas_permitidas.through,
    dispatch_uid="misc_catalog_tipo_gestion_empresas",
)
m2m_changed.connect(
    _invalidate_after_commit,
    sender=TipoGestionMuestra.pruebas_sugeridas.through,
    dispatch_uid="misc_catalog_tipo_gestion_pruebas",
)
