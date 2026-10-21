"""Read-only integrity gate for the deterministic operational seed."""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoItem,
    CriterioEvaluacionLimite,
    PruebaFuenteLimite,
    PruebaLimiteCampo,
)
from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.models.technicalCatalogs.index import CategoriaUnidad, Condicion, Unidad


class Command(BaseCommand):
    help = "Valida las relaciones que debe cumplir el seed técnico-operativo de Global Oil."

    def handle(self, *args, **options):
        errors = []

        def require_empty(queryset, message):
            count = queryset.count()
            if count:
                errors.append(f"{message}: {count} registro(s).")

        require_empty(CatalogoTecnico.objects.filter(version_actual__isnull=True), "Catálogos sin versión vigente")
        require_empty(CatalogoTecnicoItem.objects.filter(version__isnull=True), "Ítems de catálogo sin versión")
        require_empty(
            CatalogoTecnicoItem.objects.exclude(version__catalogo=F("catalogo")),
            "Ítems vinculados a una versión de otro catálogo",
        )
        require_empty(Unidad.objects.filter(categoria__isnull=True), "Unidades sin magnitud relacional")
        require_empty(
            Unidad.objects.filter(magnitud__isnull=False).exclude(magnitud=F("categoria__nombre")),
            "Etiquetas de magnitud inconsistentes con su relación",
        )
        require_empty(
            Condicion.objects.exclude(magnitud_categoria=F("unidad__categoria")),
            "Condiciones con una magnitud distinta de su unidad",
        )
        require_empty(
            CriterioEvaluacionLimite.objects.filter(catalogo_item__isnull=False).exclude(
                catalogo_item__version=F("catalogo_item__catalogo__version_actual")
            ),
            "Criterios de límite que usan ítems fuera de la versión vigente",
        )

        for prueba in Prueba.objects.filter(activo=True, deleted_at__isnull=True):
            published_sources = PruebaFuenteLimite.objects.filter(
                prueba=prueba,
                activo=True,
                publicada=True,
                deleted_at__isnull=True,
            )
            if published_sources.count() != 1:
                errors.append(
                    f"{prueba.acronimo} debe tener exactamente una versión de límites activa y publicada; "
                    f"tiene {published_sources.count()}."
                )
                continue
            if published_sources.first().tipo_limite == "sin_limite":
                continue
            if not PruebaLimiteCampo.objects.filter(
                fuente_limite=published_sources.first(),
                activo=True,
                deleted_at__isnull=True,
            ).exists():
                errors.append(f"{prueba.acronimo} no tiene campos de límite activos en su versión vigente.")

        if errors:
            raise CommandError("Seed técnico-operativo inválido:\n- " + "\n- ".join(errors))

        self.stdout.write(self.style.SUCCESS(
            "Seed técnico-operativo válido: catálogos, versiones, unidades y límites son coherentes."
        ))
