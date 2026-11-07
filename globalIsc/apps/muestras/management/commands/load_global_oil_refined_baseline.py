"""Reproducible, source-aware master and technical baseline for Global Oil."""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.activesTree.api.models.index import Lubricante
from apps.activesTree.api.models.machines.index import Maquina
from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CampoTecnicoMuestra, CatalogoTecnico, CatalogoTecnicoCampo,
    CatalogoTecnicoItem, CatalogoTecnicoItemValor, CatalogoTecnicoVersion,
    CriterioEvaluacionLimite, PruebaFuenteLimite, PruebaLimiteCampo,
)
from apps.misc.api.models.pruebas.index import (
    Prueba, PruebaResultado, PruebaResultadoComponente, PruebaResultadoDivision,
)
from apps.misc.api.models.technicalCatalogs.index import CategoriaUnidad, EquipoPrueba, MetodoEquipo, Unidad


BRAND_RULES = (
    (r"\b(?:MAXFLUID|MAXDIESEL|MAXGEAR|GLOBAL\s+(?:GAS|TDH|MAX))\b", "Global Oil", "regla_global_oil"),
    (r"\bCASTROL\b", "Castrol", "regla_castrol"),
    (r"\bMOBIL\b", "Mobil", "regla_mobil"),
    (r"\bSHELL\b", "Shell", "regla_shell"),
    (r"\bCHEVRON\b|\bDELO\b", "Chevron", "regla_chevron"),
    (r"\bDISPEL\b|\bDIS\s+ISO\b", "Dispel", "regla_dispel"),
    (r"\bELF\b", "ELF", "regla_elf"),
    (r"\bENI\b", "Eni", "regla_eni"),
    (r"\bLIQUI\s+MOLY\b", "LIQUI MOLY", "regla_liqui_moly"),
    (r"\bYAMA(?:HA|LUBE)\b", "Yamalube", "regla_yamalube"),
    (r"\bZF\b|\bLIFEGUARD\b", "ZF", "regla_zf"),
    (r"\bPETROBRAS\b", "Petrobras", "regla_petrobras"),
)
METALS = {"Ag", "Al", "B", "Ba", "Ca", "Cd", "Cr", "Cu", "Fe", "K", "Li", "Mg", "Mn", "Mo", "Na", "Ni", "P", "Pb", "Sb", "Si", "Sn", "Ti", "V", "Zn"}
PHYSICO_SPECS = (
    ("Apariencia", "organoléptico", "-", "texto"), ("Olor", "organoléptico", "-", "texto"),
    ("Viscosidad cinemática a 40 °C", "ASTM D445", "cSt", "numero"),
    ("Viscosidad cinemática a 100 °C", "ASTM D445", "cSt", "numero"),
    ("Índice de viscosidad", "ASTM D2270", "-", "numero"),
    ("Punto de chispa", "ASTM D92", "°C", "numero"), ("Densidad a 15 °C", "ASTM D4052", "g/mL", "numero"),
    ("Nitración", "ASTM D7889", "-", "numero"), ("Oxidación", "ASTM D7889", "-", "numero"),
    ("Hollín", "ASTM D7889", "%", "numero"), ("Sulfatación", "ASTM D7889", "-", "numero"),
    ("TAN", "ASTM D664", "mg KOH/g", "numero"), ("TBN", "ASTM D2896", "mg KOH/g", "numero"),
    ("Agua", "ASTM D6304", "%", "numero"), ("Nivel de contaminación", "ISO 4406", "-", "texto"),
    ("Espuma secuencia I", "ASTM D892", "mL/mL", "numero"),
    ("Espuma secuencia II", "ASTM D892", "mL/mL", "numero"),
    ("Espuma secuencia III", "ASTM D892", "mL/mL", "numero"),
)


def norm(value):
    return re.sub(r"\s*-\s*", "-", " ".join(str(value or "").split())).strip()


def code(value, limit=120):
    return slugify(norm(value)).replace("-", "_")[:limit] or "sin_valor"


def raw_rows(path):
    with path.open(encoding="utf-8") as source:
        return [json.loads(line)["data"] for line in source if line.strip()]


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def product_parts(source):
    text = norm(source)
    for pattern, brand, rule in BRAND_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            reference = re.sub(pattern, "", text, flags=re.IGNORECASE)
            reference = norm(reference).strip(" -/") or text
            return brand, reference, rule, "CONFIRMADA_POR_REGLA"
    return "", text, "sin_regla", "PENDIENTE_REVISION"


class Command(BaseCommand):
    help = "Carga maestros técnicos refinados desde staging y base de conocimiento, sin cargar muestras."

    def add_arguments(self, parser):
        parser.add_argument("--artifacts", default="outputs/migracion_historica_global_oil")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--yes", action="store_true")

    def handle(self, *args, **options):
        root = Path(options["artifacts"])
        raw_path = root / "staging" / "reportes_oa_raw.jsonl"
        measurements_path = root / "staging" / "mediciones.csv"
        metal_path = root / "catalogos_fuente" / "01_limites_metales.csv"
        viscosity_path = root / "catalogos_fuente" / "02_viscosidad.csv"
        degradation_path = root / "catalogos_fuente" / "03_degradacion.csv"
        if not all(path.is_file() for path in (raw_path, measurements_path, metal_path, viscosity_path, degradation_path)):
            raise CommandError("Faltan artefactos ETL. Ejecute la extracción antes de esta carga.")
        rows = raw_rows(raw_path)
        measurement_columns = []
        for measurement in csv_rows(measurements_path):
            column = measurement["source_column"]
            if column not in measurement_columns:
                measurement_columns.append(column)
        plan = {"empresas": len({norm(r.get('CLIENTE')) for r in rows if r.get('CLIENTE')}), "equipos": len({(norm(r.get('CLIENTE')), norm(r.get('EQUIPO'))) for r in rows if r.get('CLIENTE') and r.get('EQUIPO')}), "lubricantes": len({norm(r.get('LUBRICANTE')) for r in rows if r.get('LUBRICANTE')}), "pruebas": len(measurement_columns)}
        self.stdout.write(json.dumps(plan, ensure_ascii=False))
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulación: no se escribió en la base."))
            return
        if not options["yes"]:
            raise CommandError("Operación de escritura. Use --dry-run y luego --yes.")

        audit, pending = [], []
        with transaction.atomic():
            companies = {}
            for name in sorted({norm(r.get("CLIENTE")) for r in rows if r.get("CLIENTE")}, key=str.casefold):
                company, created = Empresa.objects.get_or_create(nombre=name, defaults={"is_active": True, "is_internal": False, "status": Empresa.Status.ACTIVE})
                companies[name] = company
                audit.append(("empresa", name, company.id, created))
            for company_name, equipment_name in sorted({(norm(r.get("CLIENTE")), norm(r.get("EQUIPO"))) for r in rows if r.get("CLIENTE") and r.get("EQUIPO")}, key=lambda item: (item[0].casefold(), item[1].casefold())):
                machine, created = Maquina.objects.get_or_create(empresa=companies[company_name], nombre=equipment_name, defaults={"codigo_equipo": equipment_name, "activo": True})
                audit.append(("maquina", f"{company_name} / {equipment_name}", machine.id, created))
            for source in sorted({norm(r.get("LUBRICANTE")) for r in rows if r.get("LUBRICANTE")}, key=str.casefold):
                brand, reference, rule, status = product_parts(source)
                lubricant, created = Lubricante.objects.get_or_create(fabricante=brand, referencia=reference, defaults={"nombre": source, "activo": status == "CONFIRMADA_POR_REGLA"})
                audit.append(("lubricante", source, lubricant.id, created))
                if status != "CONFIRMADA_POR_REGLA":
                    pending.append({"source": source, "reason": "Marca no deducible sin inventar", "target_id": lubricant.id})
            units = self._units()
            methods = self._methods(units)
            catalogs = self._catalogs(rows, viscosity_path)
            tests = self._tests(measurement_columns, methods, units)
            self._metal_limits(metal_path, catalogs["tipo"], tests)
            self._degradation_rules(degradation_path, tests)

        (root / "reports" / "carga_refinada.json").write_text(json.dumps({"plan": plan, "created": sum(1 for *_, created in audit if created), "pending_lubricants": pending, "audit": [{"entity": e, "source": s, "target_id": i, "created": c} for e, s, i, c in audit]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Carga refinada completada; pendientes de lubricante: {len(pending)}."))

    def _units(self):
        values = {"cSt": ("Viscosidad", "Centistokes"), "ppm": ("Concentración", "Partes por millón"), "%": ("Porcentaje", "Porcentaje"), "°C": ("Temperatura", "Grados Celsius"), "g/mL": ("Densidad", "Gramos por mililitro"), "mg KOH/g": ("Basicidad/acidez", "Miligramos KOH por gramo"), "mL/mL": ("Espuma", "Mililitros por mililitro"), "-": ("Adimensional", "Sin unidad")}
        result = {}
        for symbol, (category_name, unit_name) in values.items():
            category, _ = CategoriaUnidad.objects.get_or_create(nombre=category_name, defaults={"activo": True})
            result[symbol], _ = Unidad.objects.get_or_create(simbolo=symbol, defaults={"nombre": unit_name, "categoria": category, "magnitud": category_name, "activo": True})
        return result

    def _methods(self, units):
        equipment, _ = EquipoPrueba.objects.get_or_create(codigo="ETL_HISTORICO", defaults={"nombre": "Método histórico importado", "activo": True})
        result = {}
        for _display, method, _unit, _type in PHYSICO_SPECS:
            if method not in result:
                result[method], _ = MetodoEquipo.objects.get_or_create(equipo_prueba=equipment, codigo=code(method, 50), defaults={"nombre": method, "norma_referencia": method, "activo": True})
        return result

    def _catalogs(self, rows, viscosity_path):
        config = {"tipo": ("Tipo de sistema", "tipo_sistema", "Tipo"), "grado": ("Grado de viscosidad", "grado_viscosidad", "Viscosidad"), "especificacion": ("Especificación", "especificacion", "Esp_Cal")}
        result = {}
        for key, (name, catalog_code, source_column) in config.items():
            catalog, _ = CatalogoTecnico.objects.get_or_create(codigo=catalog_code, defaults={"nombre": name, "tipo_muestra": "aceite", "permite_desconocido": True, "activo": True})
            version = catalog.version_actual
            if not version:
                version, _ = CatalogoTecnicoVersion.objects.get_or_create(catalogo=catalog, numero=1, defaults={"nombre": "Fuente Excel v9", "activo": True})
                catalog.version_actual = version
                catalog.save(update_fields=["version_actual", "updated_at"])
            CampoTecnicoMuestra.objects.get_or_create(tipo_muestra="aceite", codigo=catalog_code, defaults={"nombre_visible": name, "catalogo": catalog, "permite_desconocido": True, "activo": True})
            for value in sorted({norm(row.get(source_column)) for row in rows if row.get(source_column)}, key=str.casefold):
                CatalogoTecnicoItem.objects.get_or_create(version=version, codigo=code(value), defaults={"catalogo": catalog, "nombre": value, "activo": True})
            result[key] = (catalog, version)
        catalog, version = result["grado"]
        fields = {key: CatalogoTecnicoCampo.objects.get_or_create(catalogo=catalog, codigo=key, defaults={"nombre": label, "tipo_dato": "decimal", "orden": order})[0] for order, (key, label) in enumerate((("vmin", "Viscosidad mínima"), ("vmax", "Viscosidad máxima"), ("iv", "Índice de viscosidad")), start=1)}
        for row in csv_rows(viscosity_path):
            grade = norm(row.get("col_2"))
            if not grade or grade == "Grado":
                continue
            item, _ = CatalogoTecnicoItem.objects.get_or_create(version=version, codigo=code(grade), defaults={"catalogo": catalog, "nombre": grade, "activo": True})
            for field_key, source_column in (("vmin", "col_3"), ("vmax", "col_4"), ("iv", "col_5")):
                value = norm(row.get(source_column))
                if value and value != "-":
                    CatalogoTecnicoItemValor.objects.update_or_create(item=item, campo=fields[field_key], defaults={"valor": value})
        return result

    def _tests(self, columns, methods, units):
        result, physical = {}, [column for column in columns if column not in METALS]
        ordered_physical = sorted(physical, key=lambda column: columns.index(column))
        for index, column in enumerate(ordered_physical):
            display, method, symbol, data_type = PHYSICO_SPECS[index] if index < len(PHYSICO_SPECS) else (norm(column), "", "-", "texto")
            test, _ = Prueba.objects.get_or_create(acronimo=code(display, 30), defaults={"nombre_variable": display, "unidad_medida": symbol, "unidad_catalogo": units[symbol], "metodo": methods.get(method), "activo": True})
            pr, _ = PruebaResultado.objects.get_or_create(prueba=test, acronimo=code(display, 30), defaults={"nombre": display, "unidad_medida": symbol, "unidad_catalogo": units[symbol], "activo": True})
            division, _ = PruebaResultadoDivision.objects.get_or_create(resultado=pr, nombre="Principal", defaults={"es_principal": True, "activo": True})
            component, _ = PruebaResultadoComponente.objects.get_or_create(division=division, acronimo=code(display, 30), defaults={"nombre": display, "tipo_dato": "numerico" if data_type == "numero" else "comentario", "activo": True})
            result[column] = (test, pr, division, component)
        for symbol in sorted(METALS):
            test, _ = Prueba.objects.get_or_create(acronimo=symbol, defaults={"nombre_variable": symbol, "unidad_medida": "ppm", "unidad_catalogo": units["ppm"], "activo": True})
            pr, _ = PruebaResultado.objects.get_or_create(prueba=test, acronimo=symbol, defaults={"nombre": symbol, "unidad_medida": "ppm", "unidad_catalogo": units["ppm"], "activo": True})
            division, _ = PruebaResultadoDivision.objects.get_or_create(resultado=pr, nombre="Principal", defaults={"es_principal": True, "activo": True})
            component, _ = PruebaResultadoComponente.objects.get_or_create(division=division, acronimo=symbol, defaults={"nombre": symbol, "tipo_dato": "numerico", "activo": True})
            result[symbol] = (test, pr, division, component)
        return result

    def _metal_limits(self, path, catalog_ref, tests):
        catalog, _version = catalog_ref
        field = CampoTecnicoMuestra.objects.get(codigo="tipo_sistema", tipo_muestra="aceite")
        items = {code(item.nombre): item for item in CatalogoTecnicoItem.objects.filter(catalogo=catalog)}
        rows = csv_rows(path)
        header = next(row for row in rows if row.get("col_1") == "Elemento")
        source_types = [(f"col_{index}", header.get(f"col_{index}")) for index in range(4, 14)]
        for row in rows:
            metal = norm(row.get("col_1"))
            if metal not in METALS or metal not in tests:
                continue
            test, pr, division, component = tests[metal]
            source, _ = PruebaFuenteLimite.objects.get_or_create(prueba=test, idempotency_key=f"excel-v9-metal-{metal}", defaults={"tipo_limite": "campo_muestra", "catalogo_fuente": catalog, "campo_tecnico_muestra": field, "publicada": True, "modo_seleccion": "desde_muestra_editable", "notas": "Fuente: Base_Conocimiento_Aceites_v9 / 01_Limites_Metales"})
            limit, _ = PruebaLimiteCampo.objects.get_or_create(fuente_limite=source, codigo="max_ppm", defaults={"nombre": "Máximo ppm", "operador": "max", "tipo_comparacion": "numerica", "unidad": "ppm", "resultado": pr, "division": division, "componente": component})
            for order, (column, type_name) in enumerate(source_types, start=1):
                item = items.get(code(type_name))
                value = norm(row.get(column))
                if not item or not value or value == "*":
                    continue
                CriterioEvaluacionLimite.objects.update_or_create(fuente_limite=source, codigo=code(item.nombre), defaults={"nombre": item.nombre, "tipo_criterio": "catalogo_item", "catalogo_item": item, "valores_limite": {limit.codigo: value}, "orden": order, "activo": True})

    def _degradation_rules(self, path, tests):
        for row in csv_rows(path):
            parameter, method, criterion, interpretation = (norm(row.get(key)) for key in ("col_1", "col_2", "col_4", "col_5"))
            if not parameter or parameter == "Parámetro":
                continue
            target = next((value for source, value in tests.items() if code(parameter).split("_")[0] in code(source)), None)
            if not target:
                continue
            test = target[0]
            PruebaFuenteLimite.objects.get_or_create(prueba=test, idempotency_key=f"v9-deg-{code(parameter, 50)}", defaults={"tipo_limite": "sin_limite", "politica_evaluacion": "solo_informativo", "publicada": True, "modo_seleccion": "fijo", "configuracion_regla": {"criterio_origen": criterion, "metodo_origen": method}, "notas": interpretation})
