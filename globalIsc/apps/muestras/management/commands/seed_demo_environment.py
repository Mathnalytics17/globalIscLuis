"""Crea el catálogo y escenario demostrativo completo de Global Oil.

No borra información: combine it with Django ``flush --noinput`` only when a
database de demostración haya sido confirmada como desechable.
"""

import os

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.activesTree.api.models.index import Lubricante, PuntoMuestreo
from apps.activesTree.services import ensure_machine_tree_node
from apps.activesTree.api.models.machines.index import Maquina
from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    EscalaComparacion, EscalaComparacionItem, PruebaFuenteLimite, PruebaLimiteCampo,
    normalize_scale_token,
)
from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.models.technicalCatalogs.index import Unidad
from apps.misc.api.models.tipoGestionMuestra.index import TipoGestionMuestra


TESTS = (
    ("INDVISC", "Índice de viscosidad", "cSt", "max", "170"),
    ("OXID", "Oxidación", "Abs/0.1 mm", "warn_max", "0.15"),
    ("NTR", "Nitración", "Abs/0.1 mm", "warn_max", "0.12"),
    ("ESPDES", "Desgaste elemental", "ppm", "max", "100"),
    ("AGUA", "Contenido de agua", "%", "max", "0.10"),
)

ASSETS = {
    "Empresa Minera Demo": (
        ("MIN-DRG-01", "Draga de producción 01", "Reductor transmisión principal", "MAXGEAR ISO 320"),
        ("MIN-DRG-02", "Draga de producción 02", "Sistema hidráulico de cucharas", "MAXFLUID ISO 68"),
        ("MIN-CHN-01", "Chancadora primaria", "Reductor principal", "MAXGEAR ISO 460"),
        ("MIN-MOL-01", "Molino de bolas 01", "Corona y piñón", "MAXGEAR ISO 680"),
        ("MIN-PMP-01", "Bomba de relaves 01", "Rodamiento lado acople", "MAXGREASE EP 2"),
    ),
    "Taller Demo": (
        ("TAL-CAM-01", "Camión de servicio 01", "Motor diésel", "MAXMOTOR 15W-40"),
        ("TAL-CAM-02", "Camión de servicio 02", "Diferencial trasero", "MAXGEAR 85W-140"),
        ("TAL-GEN-01", "Generador móvil 01", "Motor diésel", "MAXMOTOR 15W-40"),
    ),
    "Global Oil": (
        ("GO-LAB-01", "Banco demostrativo laboratorio", "Circuito hidráulico", "MAXFLUID ISO 46"),
        ("GO-COMP-01", "Compresor de aire 01", "Cárter del compresor", "MAXCOMP ISO 68"),
    ),
}


EXTRA_POINTS = {
    "MIN-DRG-01": ("Malacate de proa", "Sistema hidráulico principal"),
    "MIN-DRG-02": ("Reductor de giro", "Malacate de popa"),
    "MIN-CHN-01": ("Sistema hidráulico de ajuste",),
    "MIN-MOL-01": ("Chumacera lado alimentación", "Chumacera lado descarga"),
    "MIN-PMP-01": ("Rodamiento lado impulsor",),
    "TAL-CAM-01": ("Diferencial trasero", "Caja de cambios"),
    "TAL-CAM-02": ("Caja de transferencia",),
    "TAL-GEN-01": ("Sistema hidráulico auxiliar",),
    "GO-LAB-01": ("Bomba de circulación",),
    "GO-COMP-01": ("Caja de engranajes",),
}


class Command(BaseCommand):
    help = "Crea catálogo, límites, activos y tendencias sintéticas de demostración de forma idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=9, help="Muestras históricas por punto principal (2-12).")
        parser.add_argument("--reset-passwords", action="store_true", help="Restablece las ocho cuentas demo.")

    @transaction.atomic
    def handle(self, *args, **options):
        if len(os.environ.get("DEMO_DEFAULT_PASSWORD", "")) < 12:
            raise CommandError("Defina DEMO_DEFAULT_PASSWORD (mínimo 12 caracteres).")

        call_command("seed_dynamic_technical_config")
        access_args = ["--with-demo-accounts"]
        if options["reset_passwords"]:
            access_args.append("--reset-passwords")
        call_command("seed_access_baseline", *access_args)

        for symbol, name, magnitude in (("ppm", "Partes por millón", "concentración"), ("%", "Porcentaje", "proporción"), ("cSt", "Centistokes", "viscosidad"), ("Abs/0.1 mm", "Absorbancia", "FTIR")):
            Unidad.objects.update_or_create(simbolo=symbol, defaults={"nombre": name, "magnitud": magnitude, "activo": True})

        scale, _ = EscalaComparacion.objects.update_or_create(codigo="semaforo_demo", defaults={"nombre": "Semáforo de condición", "descripcion": "Escala demostrativa para la evaluación visual."})
        for order, label in enumerate(("Normal", "Alerta", "Crítico"), 1):
            EscalaComparacionItem.objects.update_or_create(escala=scale, valor_normalizado=normalize_scale_token(label), defaults={"etiqueta": label, "orden": order, "numero_base": order, "activo": True, "deleted_at": None})

        tests = {}
        for code, name, unit, operator, limit in TESTS:
            test, _ = Prueba.objects.update_or_create(acronimo=code, defaults={"nombre_variable": name, "unidad_medida": unit, "activo": True, "deleted_at": None})
            tests[code] = test
            source, _ = PruebaFuenteLimite.objects.update_or_create(prueba=test, version=1, defaults={"tipo_limite": "global", "prioridad": 1, "modo_seleccion": "fijo", "publicada": True, "activo": True, "deleted_at": None, "notas": "Límite sintético de demostración. No usar en operación real."})
            PruebaLimiteCampo.objects.update_or_create(fuente_limite=source, codigo="principal", defaults={"nombre": f"{name} principal", "operador": operator, "tipo_comparacion": "numerica", "valor_global": limit, "unidad": unit, "orden": 1, "comentario_normal": "Resultado dentro de límite demostrativo.", "comentario_fuera_limite": "Resultado fuera de límite demostrativo.", "activo": True, "deleted_at": None})

        gestion, _ = TipoGestionMuestra.objects.update_or_create(nombre="Demostración técnica", defaults={"dias_habiles": 3, "dias_calendario": 5, "aplica_a_todos": True, "activo": True, "deleted_at": None})
        gestion.pruebas_sugeridas.set(tests.values())
        for name, assets in ASSETS.items():
            company = Empresa.objects.get(nombre=name)
            for code, machine_name, point_name, oil in assets:
                maker, reference = oil.split(" ", 1)
                lubricant, _ = Lubricante.objects.update_or_create(fabricante=maker, referencia=reference, defaults={"nombre": oil, "activo": True})
                machine, _ = Maquina.objects.update_or_create(empresa=company, codigo_equipo=code, defaults={"nombre": machine_name, "descripcion": "Activo sintético de demostración.", "tipoAceite": oil, "frecuenciaCambio": "2000 horas", "frecuenciaAnalisis": "250 horas", "activo": True})
                ensure_machine_tree_node(machine)
                for point_index, current_point_name in enumerate((point_name, *EXTRA_POINTS.get(code, ())), start=1):
                    PuntoMuestreo.objects.update_or_create(
                        maquina=machine,
                        nombre=current_point_name,
                        defaults={
                            "codigo": f"{code}-PM-{point_index:02d}",
                            "descripcion": "Punto sintético de demostración.",
                            "lubricante": oil,
                            "lubricante_catalogo": lubricant,
                            "frecuencia_cambio": 2000,
                            "frecuencia_analisis": 250,
                            "activo": True,
                        },
                    )

        minera = Empresa.objects.get(nombre="Empresa Minera Demo")
        call_command("seed_trend_demo", company=str(minera.pk), months=max(2, min(options["months"], 12)))
        call_command("seed_operational_showcase")
        self.stdout.write(self.style.SUCCESS("Entorno demo listo: 8 cuentas, 3 empresas, catálogo, límites, activos, tendencias e inventario operativo."))
