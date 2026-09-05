from decimal import Decimal
import json

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify


def model(label):
    app_label, model_name = label.split(".")
    return apps.get_model(app_label, model_name)


def code(value):
    return slugify(str(value or "").strip()).replace("-", "_")


class Command(BaseCommand):
    help = (
        "Limpia datos operativos/tecnicos del flujo de laboratorio y crea una "
        "base inicial coherente. Conserva usuarios, empresas, roles y permisos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Confirma el borrado de datos.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError("Este comando borra datos. Ejecute con --yes para confirmar.")

        self._delete_flow_data()
        self._seed_technical_catalogs()
        self._seed_units_equipment_and_management_types()
        self._seed_scales()
        self._seed_tests_and_limits()
        self.stdout.write(self.style.SUCCESS("Flujo tecnico-operativo reiniciado correctamente."))

    def _delete_flow_data(self):
        labels = [
            "reporte.ReporteEnvio",
            "reporte.Reporte",
            "resultado.RevisionResultado",
            "resultado.HistoricoResultado",
            "resultado.Resultado",
            "muestras.PruebaMuestra",
            "muestras.MuestraAtributoTecnico",
            "muestras.IngresoLabLote",
            "muestras.Muestra",
            "muestras.LoteMuestras",
            "muestras.SampleBatchExcelTemplateToken",
            "activesTree.Maquina",
            "misc.LotePruebasPredefinidoDetalle",
            "misc.LotePruebasPredefinido",
            "misc.PruebaLimiteCampo",
            "misc.CriterioEvaluacionLimite",
            "misc.PruebaFuenteLimite",
            "misc.PruebaResultadoDisposicionItem",
            "misc.PruebaResultadoDisposicion",
            "misc.PruebaResultadoSeparador",
            "misc.PruebaResultadoComponente",
            "misc.PruebaResultadoDivision",
            "misc.PruebaResultado",
            "misc.Prueba",
            "misc.CatalogoTecnicoItemValor",
            "misc.CatalogoTecnicoCampo",
            "misc.CampoTecnicoMuestra",
            "misc.CatalogoTecnicoItem",
            "misc.CatalogoTecnico",
            "misc.EscalaComparacionItem",
            "misc.EscalaComparacion",
            "misc.MetodoEquipo",
            "misc.EquipoPrueba",
            "misc.Condicion",
            "misc.Unidad",
            "misc.TipoGestionMuestra",
        ]
        for label in labels:
            qs = model(label).objects.all()
            count = qs.count()
            if count:
                qs.delete()
                self.stdout.write(f"Eliminados {count} registros de {label}")

    def _catalog(self, nombre, codigo, tipo_muestra="ambos", orden=1):
        CatalogoTecnico = model("misc.CatalogoTecnico")
        return CatalogoTecnico.objects.create(
            nombre=nombre,
            codigo=codigo,
            tipo_muestra=tipo_muestra,
            es_requerido_en_muestra=False,
            permite_desconocido=True,
            orden=orden,
            activo=True,
        )

    def _catalog_item(self, catalog, nombre, metadata=None):
        CatalogoTecnicoItem = model("misc.CatalogoTecnicoItem")
        return CatalogoTecnicoItem.objects.create(
            catalogo=catalog,
            nombre=nombre,
            codigo=code(nombre),
            metadata=metadata or {},
            activo=True,
        )

    def _sample_field(self, nombre, codigo, tipo_muestra, catalog, orden, obligatorio=True):
        CampoTecnicoMuestra = model("misc.CampoTecnicoMuestra")
        return CampoTecnicoMuestra.objects.create(
            nombre_visible=nombre,
            codigo=codigo,
            tipo_muestra=tipo_muestra,
            catalogo=catalog,
            obligatorio=obligatorio,
            permite_desconocido=True,
            visible_en_ingreso=True,
            visible_en_asignacion=True,
            orden=orden,
            activo=True,
        )

    def _seed_technical_catalogs(self):
        self.catalogs = {}
        self.items = {}
        self.sample_fields = {}

        grado = self._catalog("Grado de viscosidad", "grado_viscosidad", "aceite", 1)
        nivel = self._catalog("Nivel de desempeño", "nivel_desempeno", "aceite", 2)
        uso = self._catalog("Uso", "uso", "aceite", 3)
        nlgi = self._catalog("NLGI", "nlgi", "grasa", 4)
        iso = self._catalog("Nivel de contaminación", "nivel_contaminacion", "ambos", 5)

        self.catalogs.update(grado=grado, nivel=nivel, uso=uso, nlgi=nlgi, iso=iso)

        self.sample_fields["grado"] = self._sample_field("Grado de viscosidad", "grado_viscosidad", "aceite", grado, 1)
        self.sample_fields["nivel"] = self._sample_field("Nivel de desempeño", "nivel_desempeno", "aceite", nivel, 2)
        self.sample_fields["uso"] = self._sample_field("Uso", "uso", "aceite", uso, 3)
        self.sample_fields["nlgi"] = self._sample_field("NLGI", "nlgi", "grasa", nlgi, 1)

        for name in ["SAE 10W-60", "SAE 15W-60", "SAE 20W-60", "SAE 25W-60", "SAE 60"]:
            self.items[("grado", name)] = self._catalog_item(grado, name)
        for name in ["API CI-4", "API SL", "API SN"]:
            self.items[("nivel", name)] = self._catalog_item(nivel, name)
        for name in ["Motor Diesel", "Motor Gasolina", "Hidráulico", "Transmisión", "Diferencial"]:
            self.items[("uso", name)] = self._catalog_item(uso, name)
        for name in ["1", "2", "3"]:
            self.items[("nlgi", name)] = self._catalog_item(nlgi, name)
        for name in ["23/21/17", "20/18/15", "19/17/14", "18/16/13", "17/15/12", "16/14/11", "15/13/09"]:
            parts = [int(part) for part in name.split("/")]
            self.items[("iso", name)] = self._catalog_item(iso, name, {"4um": parts[0], "6um": parts[1], "14um": parts[2]})

    def _seed_units_equipment_and_management_types(self):
        Unidad = model("misc.Unidad")
        Condicion = model("misc.Condicion")
        EquipoPrueba = model("misc.EquipoPrueba")
        MetodoEquipo = model("misc.MetodoEquipo")
        TipoGestionMuestra = model("misc.TipoGestionMuestra")

        self.units = {
            "cSt": Unidad.objects.create(nombre="Centistokes", simbolo="cSt", magnitud="viscosidad", activo=True),
            "ppm": Unidad.objects.create(nombre="Partes por millón", simbolo="ppm", magnitud="concentracion", activo=True),
            "part/ml": Unidad.objects.create(nombre="Partículas por mililitro", simbolo="partículas/ml", magnitud="conteo", activo=True),
            "C": Unidad.objects.create(nombre="Grados Celsius", simbolo="°C", magnitud="temperatura", activo=True),
            "ml/ml": Unidad.objects.create(nombre="Mililitros por mililitro", simbolo="ml/ml", magnitud="espuma", activo=True),
            "-": Unidad.objects.create(nombre="Sin unidad", simbolo="-", magnitud="adimensional", activo=True),
        }
        self.conditions = {
            "40": Condicion.objects.create(nombre="40", magnitud="temperatura", valor=Decimal("40.0000"), unidad=self.units["C"], activo=True),
            "100": Condicion.objects.create(nombre="100", magnitud="temperatura", valor=Decimal("100.0000"), unidad=self.units["C"], activo=True),
        }
        equipo = EquipoPrueba.objects.create(codigo="KHALER01", nombre="KHALER01", activo=True)
        viscosimetro = EquipoPrueba.objects.create(codigo="VISCOSIMETRO", nombre="Viscosímetro", activo=True)
        self.methods = {
            "ASTM D445": MetodoEquipo.objects.create(equipo_prueba=viscosimetro, codigo="ASTM D445", nombre="Viscosidad cinemática", activo=True),
            "ASTM D92": MetodoEquipo.objects.create(equipo_prueba=equipo, codigo="ASTM D92", nombre="Punto de chispa", activo=True),
            "ISO 4406": MetodoEquipo.objects.create(equipo_prueba=equipo, codigo="ISO 4406", nombre="Conteo de partículas", activo=True),
            "ASTM D892": MetodoEquipo.objects.create(equipo_prueba=equipo, codigo="ASTM D892", nombre="Espuma", activo=True),
        }
        TipoGestionMuestra.objects.create(nombre="Comercial", dias_habiles=0, dias_calendario=0, aplica_a_todos=True, activo=True)
        TipoGestionMuestra.objects.create(nombre="PostVenta", dias_habiles=0, dias_calendario=0, aplica_a_todos=True, activo=True)

    def _seed_scales(self):
        EscalaComparacion = model("misc.EscalaComparacion")
        EscalaComparacionItem = model("misc.EscalaComparacionItem")
        self.scales = {}
        self.scale_items = {}

        color = EscalaComparacion.objects.create(nombre="Color ASTM", codigo="color_astm", activo=True)
        olor = EscalaComparacion.objects.create(nombre="Olor", codigo="olor", activo=True)
        desgaste = EscalaComparacion.objects.create(nombre="Severidad de desgaste", codigo="severidad_desgaste", activo=True)
        self.scales.update(color=color, olor=olor, desgaste=desgaste)

        color_values = ["L0.5", "0.5", "D0.5", "L1", "1", "D1", "L1.5", "1.5", "D1.5", "L2", "2", "D2", "L2.5", "2.5", "D2.5", "L3", "3", "D3", "L3.5", "3.5", "D3.5", "L4", "4", "D4", "L4.5", "4.5", "D4.5", "L5", "5", "D5", "L5.5", "5.5", "D5.5", "L6", "6", "D6", "L6.5", "6.5", "D6.5", "L7", "7", "D7", "L7.5", "7.5", "D7.5", "L8", "8", "D8"]
        for order, label in enumerate(color_values, start=1):
            item = EscalaComparacionItem.objects.create(
                escala=color,
                etiqueta=label,
                valor_normalizado=code(label),
                orden=order,
                numero_base=Decimal(str(label.replace("L", "").replace("D", ""))),
                modificador="L" if label.startswith("L") else ("D" if label.startswith("D") else ""),
                activo=True,
            )
            self.scale_items[("color", label)] = item

        for order, label in enumerate(["Excelente", "Bueno", "Regular", "Malo", "Muy malo"], start=1):
            item = EscalaComparacionItem.objects.create(
                escala=olor,
                etiqueta=label,
                valor_normalizado=code(label),
                orden=order,
                numero_base=Decimal(order),
                activo=True,
            )
            self.scale_items[("olor", label)] = item

        for order, label in enumerate(["Normal", "Leve", "Moderado", "Severo", "Crítico"], start=1):
            item = EscalaComparacionItem.objects.create(
                escala=desgaste,
                etiqueta=label,
                valor_normalizado=code(label),
                orden=order,
                numero_base=Decimal(order - 1),
                activo=True,
            )
            self.scale_items[("desgaste", label)] = item

    def _test(self, acronimo, nombre, unidad=None, condicion=None, metodo=None):
        Prueba = model("misc.Prueba")
        return Prueba.objects.create(
            nombre_variable=nombre,
            acronimo=acronimo,
            unidad_medida=unidad.simbolo if unidad else None,
            unidad_catalogo=unidad,
            condicion_catalogo=condicion,
            condicion=str(condicion) if condicion else None,
            metodo=metodo,
            activo=True,
        )

    def _result(self, prueba, nombre, acronimo=None, components=None, separator="/"):
        PruebaResultado = model("misc.PruebaResultado")
        PruebaResultadoDivision = model("misc.PruebaResultadoDivision")
        PruebaResultadoComponente = model("misc.PruebaResultadoComponente")
        PruebaResultadoSeparador = model("misc.PruebaResultadoSeparador")
        PruebaResultadoDisposicion = model("misc.PruebaResultadoDisposicion")
        PruebaResultadoDisposicionItem = model("misc.PruebaResultadoDisposicionItem")

        result = PruebaResultado.objects.create(
            prueba=prueba,
            nombre=nombre,
            acronimo=acronimo or code(nombre).upper(),
            unidad_medida=prueba.unidad_medida,
            unidad_catalogo=prueba.unidad_catalogo,
            orden=prueba.resultados.count() + 1,
            activo=True,
        )
        division = PruebaResultadoDivision.objects.create(resultado=result, nombre="Principal", es_principal=True, orden=1, activo=True)
        disposition = PruebaResultadoDisposicion.objects.create(division=division, nombre="Disposición principal", orden=1, activo=True)
        components = components or [{"nombre": "Resultado", "acronimo": "resultado", "tipo_dato": "numerico"}]
        for index, component_data in enumerate(components, start=1):
            comp = PruebaResultadoComponente.objects.create(
                division=division,
                nombre=component_data["nombre"],
                acronimo=component_data.get("acronimo") or code(component_data["nombre"]),
                tipo_dato=component_data.get("tipo_dato", "numerico"),
                escala_comparacion=component_data.get("escala"),
                opciones_resultado=component_data.get("opciones"),
                etiqueta_verdadero=component_data.get("etiqueta_verdadero", "Sí"),
                etiqueta_falso=component_data.get("etiqueta_falso", "No"),
                requiere_valor=component_data.get("requiere_valor", True),
                orden=index,
                activo=True,
            )
            PruebaResultadoDisposicionItem.objects.create(disposicion=disposition, tipo="componente", componente=comp, orden=(index * 2) - 1)
            if index < len(components):
                sep = PruebaResultadoSeparador.objects.create(division=division, simbolo=separator, orden=index, activo=True)
                PruebaResultadoDisposicionItem.objects.create(disposicion=disposition, tipo="separador", separador=sep, orden=index * 2)
        return result

    def _source(
        self,
        prueba,
        tipo,
        catalog=None,
        sample_field=None,
        policy="todas_deben_cumplir",
        min_ok=None,
        config=None,
    ):
        PruebaFuenteLimite = model("misc.PruebaFuenteLimite")
        return PruebaFuenteLimite.objects.create(
            prueba=prueba,
            tipo_limite=tipo,
            catalogo_fuente=catalog,
            campo_tecnico_muestra=sample_field,
            politica_evaluacion=policy,
            minimo_campos_cumplidos=min_ok,
            configuracion_regla=config or {},
            activo=True,
        )

    def _limit_field(self, source, component, operador="max", tipo="numerica", escala=None, unidad=None, valor_global=None, eval_options=None, order=1):
        PruebaLimiteCampo = model("misc.PruebaLimiteCampo")
        division = component.division
        return PruebaLimiteCampo.objects.create(
            fuente_limite=source,
            nombre=f"{division.resultado.nombre} {component.acronimo or component.nombre}",
            codigo=f"{code(division.resultado.nombre)}_{code(component.acronimo or component.nombre)}_{code(operador)}",
            operador=operador,
            tipo_comparacion=tipo,
            escala_comparacion=escala,
            modo_ordinal="orden",
            unidad=unidad,
            valor_global=valor_global,
            evaluacion_opciones=eval_options,
            resultado=division.resultado,
            division=division,
            componente=component,
            orden=order,
            activo=True,
        )

    def _values_for_catalog(self, field, values_by_item_name):
        CriterioEvaluacionLimite = model("misc.CriterioEvaluacionLimite")
        for item_name, value in values_by_item_name.items():
            catalog_key = None
            for key, item in self.items.items():
                if item.nombre == item_name:
                    catalog_key = key
                    break
            if not catalog_key:
                continue
            item = self.items[catalog_key]
            criterion, _ = CriterioEvaluacionLimite.objects.get_or_create(
                fuente_limite=field.fuente_limite,
                codigo=item.codigo,
                defaults={
                    "nombre": item.nombre,
                    "tipo_criterio": "catalogo_item",
                    "catalogo_item": item,
                    "orden": field.fuente_limite.criterios.count() + 1,
                    "activo": True,
                },
            )
            values = criterion.valores_limite if isinstance(criterion.valores_limite, dict) else {}
            values[field.codigo] = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
            criterion.nombre = item.nombre
            criterion.tipo_criterio = "catalogo_item"
            criterion.catalogo_item = item
            criterion.valores_limite = values
            criterion.activo = True
            criterion.deleted_at = None
            criterion.save()

    def _seed_tests_and_limits(self):
        CriterioEvaluacionLimite = model("misc.CriterioEvaluacionLimite")

        visc = self._test("vis@40", "Viscosidad@40", self.units["cSt"], self.conditions["40"], self.methods["ASTM D445"])
        self._result(visc, "Viscosidad@40", "vis@40", [{"nombre": "Viscosidad@40", "acronimo": "vis@40", "tipo_dato": "numerico", "unidad": "cSt"}])
        visc_comp = visc.resultados.first().divisiones.first().componentes.first()
        visc_source = self._source(visc, "campo_muestra", catalog=self.catalogs["grado"], sample_field=self.sample_fields["grado"])
        visc_min = self._limit_field(visc_source, visc_comp, "min", "numerica", unidad="cSt", order=1)
        visc_max = self._limit_field(visc_source, visc_comp, "max", "numerica", unidad="cSt", order=2)
        for field, values in [
            (visc_min, {"SAE 10W-60": 20, "SAE 15W-60": 25, "SAE 20W-60": 30, "SAE 25W-60": 35, "SAE 60": 40}),
            (visc_max, {"SAE 10W-60": 40, "SAE 15W-60": 45, "SAE 20W-60": 50, "SAE 25W-60": 55, "SAE 60": 65}),
        ]:
            self._values_for_catalog(field, values)

        flash = self._test("PCHISPA", "Punto de chispa", self.units["C"], None, self.methods["ASTM D92"])
        self._result(flash, "Punto de chispa", "PCHISPA", [{"nombre": "Punto de chispa", "acronimo": "PCHISPA", "tipo_dato": "numerico", "unidad": "°C"}])
        flash_comp = flash.resultados.first().divisiones.first().componentes.first()
        flash_source = self._source(flash, "campo_muestra", catalog=self.catalogs["nivel"], sample_field=self.sample_fields["nivel"])
        flash_min = self._limit_field(flash_source, flash_comp, "min", "numerica", unidad="°C")
        self._values_for_catalog(flash_min, {"API CI-4": 180, "API SL": 190, "API SN": 200})

        contamination = self._test("NVLCONTAMINACION", "Nivel de contaminación", self.units["-"], None, self.methods["ISO 4406"])
        self._result(contamination, "Código ISO", "ISO", [
            {"nombre": "4um", "acronimo": "4um", "tipo_dato": "numerico"},
            {"nombre": "6um", "acronimo": "6um", "tipo_dato": "numerico"},
            {"nombre": "14um", "acronimo": "14um", "tipo_dato": "numerico"},
        ])
        iso_source = self._source(contamination, "seleccion_asignacion", catalog=self.catalogs["iso"], policy="todas_deben_cumplir")
        for index, comp in enumerate(contamination.resultados.first().divisiones.first().componentes.all(), start=1):
            field = self._limit_field(iso_source, comp, "max", "numerica", order=index)
            values = {item.nombre: item.metadata.get(comp.acronimo) for key, item in self.items.items() if key[0] == "iso"}
            self._values_for_catalog(field, values)
        for index, key in enumerate([("iso", "23/21/17"), ("iso", "20/18/15"), ("iso", "19/17/14"), ("iso", "18/16/13"), ("iso", "17/15/12"), ("iso", "16/14/11"), ("iso", "15/13/09")], start=1):
            item = self.items[key]
            criterion, _ = CriterioEvaluacionLimite.objects.get_or_create(
                fuente_limite=iso_source,
                codigo=item.codigo,
                defaults={"nombre": item.nombre, "tipo_criterio": "catalogo_item", "catalogo_item": item},
            )
            criterion.nombre = item.nombre
            criterion.tipo_criterio = "catalogo_item"
            criterion.catalogo_item = item
            criterion.orden = index
            criterion.activo = True
            criterion.deleted_at = None
            criterion.save()

        solids = self._test("PRESOL", "Presencia de sólidos", self.units["-"])
        self._result(solids, "Presencia de sólidos", "PRESOL", [{"nombre": "Presencia de sólidos", "acronimo": "PRESOL", "tipo_dato": "booleano", "opciones": ["Si", "No"]}])
        solids_comp = solids.resultados.first().divisiones.first().componentes.first()
        solids_source = self._source(solids, "global")
        self._limit_field(solids_source, solids_comp, "eq", "booleano", valor_global=None, eval_options={"si": {"estado": "FUERA_DE_LIMITE"}, "no": {"estado": "NORMAL"}}, order=1)
        for index, value in enumerate(["No", "Si"], start=1):
            CriterioEvaluacionLimite.objects.create(fuente_limite=solids_source, nombre=f"Debe ser {value}", codigo=f"debe_ser_{code(value)}", tipo_criterio="booleano", valor=value, orden=index, activo=True)

        olor = self._test("OLOR", "Olor", self.units["-"])
        self._result(olor, "Olor", "OLOR", [{"nombre": "Olor", "acronimo": "OLOR", "tipo_dato": "escala", "escala": self.scales["olor"]}])
        olor_comp = olor.resultados.first().divisiones.first().componentes.first()
        olor_source = self._source(olor, "global")
        self._limit_field(olor_source, olor_comp, "scale_max", "escala", escala=self.scales["olor"], order=1)
        for index, label in enumerate(["Excelente", "Bueno", "Regular", "Malo", "Muy malo"], start=1):
            item = self.scale_items[("olor", label)]
            CriterioEvaluacionLimite.objects.create(fuente_limite=olor_source, nombre=f"Máximo {label}", codigo=f"maximo_{code(label)}", tipo_criterio="escala_item", escala_item=item, orden=index, activo=True)

        color = self._test("COLOR", "Color", self.units["-"])
        self._result(color, "Color", "COLOR", [{"nombre": "Color", "acronimo": "COLOR", "tipo_dato": "escala", "escala": self.scales["color"]}])
        color_comp = color.resultados.first().divisiones.first().componentes.first()
        color_source = self._source(color, "global")
        self._limit_field(color_source, color_comp, "scale_max", "escala", escala=self.scales["color"], order=1)
        for index, label in enumerate(["3", "3.5", "4", "4.5", "5"], start=1):
            item = self.scale_items[("color", label)]
            CriterioEvaluacionLimite.objects.create(fuente_limite=color_source, nombre=f"Máximo {label}", codigo=f"maximo_{code(label)}", tipo_criterio="escala_item", escala_item=item, orden=index, activo=True)

        foam = self._test("ESP", "Espuma", self.units["ml/ml"], None, self.methods["ASTM D892"])
        for seq, comps in [
            ("Secuencia I", [("EI", "EI"), ("FI", "FI")]),
            ("Secuencia II", [("EII", "EII"), ("FII", "FII")]),
            ("Secuencia III", [("EIII", "EIII"), ("FIII", "FIII")]),
        ]:
            self._result(foam, seq, code(seq).upper(), [{"nombre": name, "acronimo": acr, "tipo_dato": "numerico", "unidad": "ml/ml"} for name, acr in comps])
        foam_source = self._source(
            foam,
            "campo_muestra",
            catalog=self.catalogs["nivel"],
            sample_field=self.sample_fields["nivel"],
            policy="todas_deben_cumplir",
        )
        foam_values = {
            "EI": {"API CI-4": 11, "API SL": 10, "API SN": 10},
            "FI": {"API CI-4": 0, "API SL": 0, "API SN": 0},
            "EII": {"API CI-4": 25, "API SL": 25, "API SN": 25},
            "FII": {"API CI-4": 0, "API SL": 0, "API SN": 0},
            "EIII": {"API CI-4": 11, "API SL": 10, "API SN": 10},
            "FIII": {"API CI-4": 0, "API SL": 0, "API SN": 0},
        }
        order = 1
        for result in foam.resultados.all():
            for comp in result.divisiones.first().componentes.all():
                field = self._limit_field(foam_source, comp, "max", "numerica", unidad="ml/ml", order=order)
                self._values_for_catalog(field, {
                    item_name: {
                        "max_aceptable": maximum,
                        "max_critico": maximum + (5 if maximum else 2),
                        "usar_amarillo": True,
                    }
                    for item_name, maximum in foam_values.get(comp.acronimo, {}).items()
                })
                order += 1

        ferro = self._test("FERRO", "Ferrografía analítica", self.units["part/ml"])
        metallic = self._result(ferro, "Partículas metálicas", "PM", [
            {"nombre": "Partículas ferrosas grandes", "acronimo": "PFG", "tipo_dato": "numerico"},
            {"nombre": "Partículas ferrosas finas", "acronimo": "PFF", "tipo_dato": "numerico"},
            {"nombre": "Partículas no ferrosas", "acronimo": "PNF", "tipo_dato": "numerico"},
        ])
        morphology = self._result(ferro, "Morfología de desgaste", "MORF", [
            {"nombre": "Desgaste por corte", "acronimo": "CORTE", "tipo_dato": "escala", "escala": self.scales["desgaste"]},
            {"nombre": "Desgaste por fatiga", "acronimo": "FATIGA", "tipo_dato": "escala", "escala": self.scales["desgaste"]},
            {"nombre": "Desgaste adhesivo", "acronimo": "ADHESIVO", "tipo_dato": "escala", "escala": self.scales["desgaste"]},
            {"nombre": "Óxidos", "acronimo": "OXIDOS", "tipo_dato": "escala", "escala": self.scales["desgaste"]},
        ])
        alerts = self._result(ferro, "Alertas críticas", "ALERTAS", [
            {"nombre": "Partículas laminares severas", "acronimo": "LAMINARES", "tipo_dato": "booleano", "etiqueta_verdadero": "Presente", "etiqueta_falso": "Ausente"},
            {"nombre": "Partículas de corte severo", "acronimo": "CORTE_SEVERO", "tipo_dato": "booleano", "etiqueta_verdadero": "Presente", "etiqueta_falso": "Ausente"},
            {"nombre": "Partículas de fatiga severa", "acronimo": "FATIGA_SEVERA", "tipo_dato": "booleano", "etiqueta_verdadero": "Presente", "etiqueta_falso": "Ausente"},
        ])
        self._result(ferro, "Observación microscópica", "OBS", [
            {"nombre": "Comentario técnico", "acronimo": "COMENTARIO", "tipo_dato": "comentario", "requiere_valor": False},
            {"nombre": "Recomendación", "acronimo": "RECOMENDACION", "tipo_dato": "comentario", "requiere_valor": False},
        ])
        ferro_source = self._source(ferro, "global")
        for order, comp in enumerate(metallic.divisiones.first().componentes.all(), start=1):
            acceptable = {"PFG": 120, "PFF": 350, "PNF": 40}[comp.acronimo]
            self._limit_field(
                ferro_source,
                comp,
                "max",
                "numerica",
                unidad="partículas/ml",
                valor_global=json.dumps({
                    "max_aceptable": acceptable,
                    "max_critico": acceptable * 2,
                    "usar_amarillo": True,
                }),
                order=order,
            )
        next_order = 4
        for comp in morphology.divisiones.first().componentes.all():
            self._limit_field(
                ferro_source,
                comp,
                "scale_max",
                "escala",
                escala=self.scales["desgaste"],
                valor_global=json.dumps({
                    "max_aceptable": "Moderado",
                    "max_critico": "Severo",
                    "usar_amarillo": True,
                }, ensure_ascii=False),
                order=next_order,
            )
            next_order += 1
        for comp in alerts.divisiones.first().componentes.all():
            self._limit_field(
                ferro_source,
                comp,
                "eq",
                "booleano",
                valor_global=json.dumps({"valor_esperado": "false"}),
                order=next_order,
            )
            next_order += 1

        sensory = self._test("SENSORIAL", "Panel sensorial estructurado", self.units["-"])
        sensory_result = self._result(sensory, "Evaluación sensorial", "SENSORIAL", [
            {"nombre": "Apariencia", "acronimo": "APARIENCIA", "tipo_dato": "escala", "escala": self.scales["olor"]},
            {"nombre": "Olor atípico", "acronimo": "OLOR_ATIPICO", "tipo_dato": "booleano", "etiqueta_verdadero": "Detectado", "etiqueta_falso": "No detectado"},
            {"nombre": "Sedimento visible", "acronimo": "SEDIMENTO", "tipo_dato": "booleano", "etiqueta_verdadero": "Presente", "etiqueta_falso": "Ausente"},
            {"nombre": "Comentario", "acronimo": "COMENTARIO", "tipo_dato": "comentario", "requiere_valor": False},
        ])
        sensory_source = self._source(sensory, "global")
        sensory_components = list(sensory_result.divisiones.first().componentes.all())
        self._limit_field(
            sensory_source,
            sensory_components[0],
            "scale_max",
            "escala",
            escala=self.scales["olor"],
            valor_global=json.dumps({"max_aceptable": "Regular", "max_critico": "Malo", "usar_amarillo": True}),
            order=1,
        )
        for order, comp in enumerate(sensory_components[1:3], start=2):
            self._limit_field(
                sensory_source,
                comp,
                "eq",
                "booleano",
                valor_global=json.dumps({"valor_esperado": "false"}),
                order=order,
            )

        condition = self._test("CONDICION", "Condición fisicoquímica básica", self.units["-"])
        water = self._result(condition, "Agua y sedimentos", "AGUA", [
            {"nombre": "Agua", "acronimo": "AGUA", "tipo_dato": "numerico"},
            {"nombre": "Sedimentos", "acronimo": "SEDIMENTOS", "tipo_dato": "numerico"},
        ])
        acidity = self._result(condition, "Acidez", "TAN", [
            {"nombre": "TAN", "acronimo": "TAN", "tipo_dato": "numerico"},
        ])
        condition_source = self._source(condition, "global")
        limits = {"AGUA": (0.10, 0.30), "SEDIMENTOS": (0.05, 0.15), "TAN": (2.0, 3.5)}
        order = 1
        for result in [water, acidity]:
            for comp in result.divisiones.first().componentes.all():
                acceptable, critical = limits[comp.acronimo]
                self._limit_field(
                    condition_source,
                    comp,
                    "max",
                    "numerica",
                    valor_global=json.dumps({
                        "max_aceptable": acceptable,
                        "max_critico": critical,
                        "usar_amarillo": True,
                    }),
                    order=order,
                )
                order += 1

        comments = self._test("SOLCO", "Prueba solo comentario", self.units["-"])
        self._result(comments, "Observación", "OBS", [
            {"nombre": "Comentario técnico", "acronimo": "COMENTARIO", "tipo_dato": "comentario"},
            {"nombre": "Recomendación", "acronimo": "RECOMENDACION", "tipo_dato": "comentario", "requiere_valor": False},
        ])
        self._source(comments, "sin_limite", policy="solo_informativo")
