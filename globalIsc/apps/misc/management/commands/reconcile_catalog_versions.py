"""Repair legacy catalog items that were created before catalog editions existed.

The command is deliberately non-destructive: it only creates a missing initial
edition and assigns items whose ``version`` is null.  It never removes, edits,
or moves items that already belong to an edition.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max

from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoItem,
    CatalogoTecnicoVersion,
)


class Command(BaseCommand):
    help = (
        "Vincula sin borrar los ítems heredados de catálogos a una versión "
        "vigente. Use --apply para realizar los cambios."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica la reparación. Sin esta opción solo muestra el diagnóstico.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        apply = options["apply"]
        catalogs = CatalogoTecnico.objects.prefetch_related("versiones", "items").order_by("id")
        repaired_items = 0
        created_versions = 0
        conflicts = 0

        for catalogo in catalogs:
            legacy_items = list(catalogo.items.filter(version__isnull=True).order_by("id"))
            current = self._valid_current_version(catalogo)

            if not current:
                current = self._latest_active_version(catalogo)
            if not current:
                next_number = (catalogo.versiones.aggregate(maximo=Max("numero"))["maximo"] or 0) + 1
                if apply:
                    current = CatalogoTecnicoVersion.objects.create(
                        catalogo=catalogo,
                        numero=next_number,
                        nombre="Versión inicial",
                        activo=True,
                    )
                created_versions += 1

            version_label = f"v{current.numero}" if current else f"v{next_number} (por crear)"
            if current and catalogo.version_actual_id != current.id:
                if apply:
                    catalogo.version_actual = current
                    catalogo.save(update_fields=["version_actual", "updated_at"])

            if not legacy_items:
                continue

            existing_codes = set()
            if current:
                existing_codes = set(current.items.values_list("codigo", flat=True))
            transferable = [item for item in legacy_items if item.codigo not in existing_codes]
            duplicate_codes = sorted({item.codigo for item in legacy_items if item.codigo in existing_codes})
            conflicts += len(duplicate_codes)

            self.stdout.write(
                f"{catalogo.nombre}: {len(transferable)} ítem(s) sin versión -> {version_label}"
            )
            if duplicate_codes:
                self.stdout.write(self.style.WARNING(
                    f"{catalogo.nombre}: se conservaron sin mover códigos duplicados: "
                    f"{', '.join(duplicate_codes)}"
                ))
            if apply and transferable:
                CatalogoTecnicoItem.objects.filter(pk__in=[item.pk for item in transferable]).update(version=current)
            repaired_items += len(transferable)

        mode = "aplicada" if apply else "simulada"
        self.stdout.write(self.style.SUCCESS(
            f"Reparación {mode}: {repaired_items} ítem(s) vinculados, "
            f"{created_versions} versión(es) creadas, {conflicts} conflicto(s) conservados."
        ))

    @staticmethod
    def _valid_current_version(catalogo):
        version = catalogo.version_actual
        if (
            version
            and version.catalogo_id == catalogo.id
            and version.activo
            and version.deleted_at is None
        ):
            return version
        return None

    @staticmethod
    def _latest_active_version(catalogo):
        return (
            catalogo.versiones.filter(activo=True, deleted_at__isnull=True)
            .order_by("-numero", "-id")
            .first()
        )
