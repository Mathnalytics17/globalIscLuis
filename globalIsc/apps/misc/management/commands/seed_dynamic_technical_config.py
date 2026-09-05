from django.core.management.base import BaseCommand
from django.db import transaction

from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoCampo,
    CampoTecnicoMuestra,
)


CATALOGS = [
    {
        "nombre": "Fabricante",
        "codigo": "fabricante",
        "tipo_muestra": "ambos",
        "es_requerido_en_muestra": True,
        "permite_desconocido": True,
        "orden": 10,
        "campos": [],
    },
    {
        "nombre": "Grado de viscosidad",
        "codigo": "grado_viscosidad",
        "tipo_muestra": "aceite",
        "es_requerido_en_muestra": True,
        "permite_desconocido": True,
        "orden": 20,
        "campos": [
            ("VMIN", "vmin", "decimal"),
            ("VMAX", "vmax", "decimal"),
            ("IV1", "iv1", "decimal"),
            ("IV2", "iv2", "decimal"),
        ],
    },
    {
        "nombre": "Nivel de desempeno",
        "codigo": "nivel_desempeno",
        "tipo_muestra": "aceite",
        "es_requerido_en_muestra": True,
        "permite_desconocido": True,
        "orden": 30,
        "campos": [
            ("Punto de chispa minimo", "punto_chispa_minimo", "decimal"),
            ("Espuma I FI", "espuma_i_fi", "decimal"),
            ("Espuma I EI", "espuma_i_ei", "decimal"),
            ("Espuma II FII", "espuma_ii_fii", "decimal"),
            ("Espuma II EII", "espuma_ii_eii", "decimal"),
            ("Espuma III FIII", "espuma_iii_fiii", "decimal"),
            ("Espuma III EIII", "espuma_iii_eiii", "decimal"),
        ],
    },
    {
        "nombre": "Uso",
        "codigo": "uso",
        "tipo_muestra": "aceite",
        "es_requerido_en_muestra": True,
        "permite_desconocido": True,
        "orden": 40,
        "campos": [
            ("Aluminio maximo", "aluminio_maximo", "decimal"),
            ("Cobre maximo", "cobre_maximo", "decimal"),
            ("Hierro maximo", "hierro_maximo", "decimal"),
            ("Silicio maximo", "silicio_maximo", "decimal"),
            ("Estano maximo", "estano_maximo", "decimal"),
        ],
    },
    {
        "nombre": "NLGI",
        "codigo": "nlgi",
        "tipo_muestra": "grasa",
        "es_requerido_en_muestra": True,
        "permite_desconocido": True,
        "orden": 50,
        "campos": [],
    },
    {
        "nombre": "Aditivo",
        "codigo": "aditivo",
        "tipo_muestra": "grasa",
        "es_requerido_en_muestra": True,
        "permite_desconocido": True,
        "orden": 60,
        "campos": [],
    },
    {
        "nombre": "Espesante",
        "codigo": "espesante",
        "tipo_muestra": "grasa",
        "es_requerido_en_muestra": True,
        "permite_desconocido": True,
        "orden": 70,
        "campos": [],
    },
]

SAMPLE_FIELDS = {
    "grado_viscosidad": {
        "nombre_visible": "Grado de viscosidad",
        "tipo_muestra": "aceite",
        "orden": 1,
    },
    "nivel_desempeno": {
        "nombre_visible": "Nivel de desempeno",
        "tipo_muestra": "aceite",
        "orden": 2,
    },
    "uso": {
        "nombre_visible": "Uso",
        "tipo_muestra": "aceite",
        "orden": 3,
    },
    "nlgi": {
        "nombre_visible": "NLGI",
        "tipo_muestra": "grasa",
        "orden": 1,
    },
}


class Command(BaseCommand):
    help = "Crea catalogos tecnicos dinamicos iniciales de forma idempotente."

    @transaction.atomic
    def handle(self, *args, **options):
        for catalog_data in CATALOGS:
            catalog_defaults = catalog_data.copy()
            fields = catalog_defaults.pop("campos")
            catalog, _ = CatalogoTecnico.objects.update_or_create(
                codigo=catalog_defaults["codigo"],
                defaults=catalog_defaults,
            )
            sample_field = SAMPLE_FIELDS.get(catalog.codigo)
            if sample_field:
                CampoTecnicoMuestra.objects.update_or_create(
                    tipo_muestra=sample_field["tipo_muestra"],
                    codigo=catalog.codigo,
                    defaults={
                        "nombre_visible": sample_field["nombre_visible"],
                        "catalogo": catalog,
                        "obligatorio": True,
                        "permite_desconocido": True,
                        "visible_en_ingreso": True,
                        "visible_en_asignacion": True,
                        "orden": sample_field["orden"],
                        "activo": True,
                        "deleted_at": None,
                    },
                )
            for order, (name, code, data_type) in enumerate(fields, start=1):
                CatalogoTecnicoCampo.objects.update_or_create(
                    catalogo=catalog,
                    codigo=code,
                    defaults={
                        "nombre": name,
                        "tipo_dato": data_type,
                        "orden": order,
                        "activo": True,
                        "deleted_at": None,
                    },
                )
            self.stdout.write(self.style.SUCCESS(f"Catalogo listo: {catalog.codigo}"))
