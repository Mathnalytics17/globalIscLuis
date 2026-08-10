from rest_framework import serializers

from apps.misc.api.serializers.technicalCatalogs.index import (
    CondicionSerializer,
    MetodoEquipoSerializer,
    UnidadSerializer,
)
from apps.misc.api.models.pruebas.index import (
    Prueba,
    PruebaResultado,
    PruebaResultadoDivision,
    PruebaResultadoComponente,
    PruebaResultadoSeparador,
    PruebaResultadoDisposicion,
    PruebaResultadoDisposicionItem,
)


def _format_decimal(value):
    if value is None:
        return ""
    text = f"{value.normalize():f}" if hasattr(value, "normalize") else str(value)
    return text.rstrip("0").rstrip(".") if "." in text else text


def format_condition_label(condition):
    if not condition:
        return None
    value = _format_decimal(condition.valor)
    symbol = getattr(condition.unidad, "simbolo", "")
    return f"{value} {symbol}".strip() or condition.nombre


class PruebaResultadoComponenteSerializer(serializers.ModelSerializer):
    temp_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    escala_comparacion_info = serializers.SerializerMethodField()

    class Meta:
        model = PruebaResultadoComponente
        fields = [
            "id", "temp_id", "nombre", "acronimo", "tipo_dato",
            "escala_comparacion", "escala_comparacion_info", "opciones_resultado", "requiere_valor", "permite_observacion",
            "etiqueta_verdadero", "etiqueta_falso",
            "orden", "activo",
        ]
        read_only_fields = ["id", "escala_comparacion_info"]

    def get_escala_comparacion_info(self, obj):
        escala = getattr(obj, "escala_comparacion", None)
        if not escala:
            return None
        return {
            "id": escala.id,
            "nombre": escala.nombre,
            "codigo": escala.codigo,
            "items": [
                {
                    "id": item.id,
                    "etiqueta": item.etiqueta,
                    "valor_normalizado": item.valor_normalizado,
                    "orden": item.orden,
                    "activo": item.activo,
                }
                for item in escala.items.filter(activo=True, deleted_at__isnull=True).order_by("orden", "id")
            ],
        }

    def validate(self, attrs):
        tipo_dato = {
            "escala_ordinal": "escala",
            "opcion": "escala",
            "texto": "comentario",
        }.get(attrs.get("tipo_dato"), attrs.get("tipo_dato"))
        if tipo_dato == "escala" and not attrs.get("escala_comparacion"):
            raise serializers.ValidationError({"escala_comparacion": "Seleccione la escala del campo en la estructura de la prueba."})
        return attrs


class PruebaResultadoSeparadorSerializer(serializers.ModelSerializer):
    temp_id = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = PruebaResultadoSeparador
        fields = ["id", "temp_id", "simbolo", "orden", "activo"]
        read_only_fields = ["id"]


class PruebaResultadoDisposicionItemSerializer(serializers.ModelSerializer):
    # En creaciÃ³n el frontend manda IDs temporales de componentes/separadores, no PK reales.
    # Por eso estos campos son texto y se resuelven manualmente en _replace_resultados().
    componente = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    separador = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    componente_label = serializers.SerializerMethodField()
    separador_label = serializers.SerializerMethodField()

    class Meta:
        model = PruebaResultadoDisposicionItem
        fields = [
            "id", "tipo", "componente", "componente_label", "separador", "separador_label", "orden",
        ]
        read_only_fields = ["id", "componente_label", "separador_label"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["componente"] = instance.componente_id
        data["separador"] = instance.separador_id
        return data

    def get_componente_label(self, obj):
        if obj.componente:
            return obj.componente.acronimo or obj.componente.nombre
        return None

    def get_separador_label(self, obj):
        if obj.separador:
            return obj.separador.simbolo
        return None


class PruebaResultadoDisposicionSerializer(serializers.ModelSerializer):
    temp_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    items = PruebaResultadoDisposicionItemSerializer(many=True, required=False)

    class Meta:
        model = PruebaResultadoDisposicion
        fields = ["id", "temp_id", "nombre", "orden", "activo", "items"]
        read_only_fields = ["id"]


class PruebaResultadoDivisionSerializer(serializers.ModelSerializer):
    temp_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    componentes = PruebaResultadoComponenteSerializer(many=True, required=False)
    separadores = PruebaResultadoSeparadorSerializer(many=True, required=False)
    disposiciones = PruebaResultadoDisposicionSerializer(many=True, required=False)

    class Meta:
        model = PruebaResultadoDivision
        fields = [
            "id", "temp_id", "nombre", "es_principal", "orden", "activo",
            "componentes", "separadores", "disposiciones",
        ]
        read_only_fields = ["id"]


class PruebaResultadoSerializer(serializers.ModelSerializer):
    temp_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    divisiones = PruebaResultadoDivisionSerializer(many=True, required=False)
    unidad_catalogo_info = UnidadSerializer(source="unidad_catalogo", read_only=True)

    class Meta:
        model = PruebaResultado
        fields = [
            "id", "temp_id", "nombre", "acronimo", "descripcion",
            "unidad_medida", "unidad_catalogo", "unidad_catalogo_info",
            "orden", "activo", "divisiones",
        ]
        read_only_fields = ["id", "unidad_catalogo_info"]


class PruebaResultadoResumenSerializer(serializers.ModelSerializer):
    unidad_catalogo_info = UnidadSerializer(source="unidad_catalogo", read_only=True)

    class Meta:
        model = PruebaResultado
        fields = [
            "id",
            "nombre",
            "acronimo",
            "unidad_medida",
            "unidad_catalogo",
            "unidad_catalogo_info",
            "orden",
            "activo",
        ]


class PruebaListSerializer(serializers.ModelSerializer):
    metodo_detalle = MetodoEquipoSerializer(source="metodo", read_only=True)
    unidad_catalogo_info = UnidadSerializer(source="unidad_catalogo", read_only=True)
    condicion_catalogo_info = CondicionSerializer(source="condicion_catalogo", read_only=True)
    equipo = serializers.SerializerMethodField()
    total_resultados = serializers.SerializerMethodField()
    total_divisiones = serializers.SerializerMethodField()
    total_componentes = serializers.SerializerMethodField()
    unidades_resultados = serializers.SerializerMethodField()
    resultados = PruebaResultadoResumenSerializer(many=True, read_only=True)

    class Meta:
        model = Prueba
        fields = [
            "id",
            "nombre_variable",
            "condicion",
            "acronimo",
            "unidad_medida",
            "unidad_catalogo",
            "unidad_catalogo_info",
            "condicion_catalogo",
            "condicion_catalogo_info",
            "metodo",
            "metodo_detalle",
            "equipo",
            "activo",
            "deleted_at",
            "created_at",
            "updated_at",
            "total_resultados",
            "total_divisiones",
            "total_componentes",
            "unidades_resultados",
            "resultados",
        ]

    def get_equipo(self, obj):
        metodo = getattr(obj, "metodo", None)

        if not metodo:
            return None

        equipo = getattr(metodo, "equipo_prueba", None)

        if not equipo:
            return None

        return {
            "id": equipo.id,
            "codigo": getattr(equipo, "codigo", None),
            "nombre": getattr(equipo, "nombre", None),
            "descripcion": getattr(equipo, "descripcion", None),
            "activo": getattr(equipo, "activo", None),
        }

    def get_total_resultados(self, obj):
        return obj.resultados.filter(activo=True).count()

    def get_total_divisiones(self, obj):
        return PruebaResultadoDivision.objects.filter(
            resultado__prueba=obj,
            activo=True
        ).count()

    def get_total_componentes(self, obj):
        return PruebaResultadoComponente.objects.filter(
            division__resultado__prueba=obj,
            activo=True
        ).count()

    def get_unidades_resultados(self, obj):
        return list(
            obj.resultados.filter(activo=True)
            .exclude(unidad_medida__isnull=True)
            .exclude(unidad_medida="")
            .values_list("unidad_medida", flat=True)
            .distinct()
        )
class PruebaDetailSerializer(serializers.ModelSerializer):
    metodo_detalle = MetodoEquipoSerializer(source="metodo", read_only=True)
    unidad_catalogo_info = UnidadSerializer(source="unidad_catalogo", read_only=True)
    condicion_catalogo_info = CondicionSerializer(source="condicion_catalogo", read_only=True)
    equipo = serializers.SerializerMethodField()
    resultados = PruebaResultadoSerializer(many=True, required=False)

    class Meta:
        model = Prueba
        fields = [
            "id", "nombre_variable", "condicion", "acronimo", "unidad_medida", "metodo",
            "unidad_catalogo", "unidad_catalogo_info", "condicion_catalogo", "condicion_catalogo_info",
            "metodo_detalle", "equipo", "activo", "deleted_at", "created_at", "updated_at",
            "resultados",
        ]
        read_only_fields = ["id", "deleted_at", "created_at", "updated_at"]

    def get_equipo(self, obj):
        return PruebaListSerializer().get_equipo(obj)


class PruebaCreateUpdateSerializer(serializers.ModelSerializer):
    # IMPORTANTE:
    # En create/update NO usamos PruebaResultadoSerializer como nested serializer,
    # porque los items de disposiciÃ³n llegan con temp_id strings del frontend
    # (ej: cmp_..., sep_...). Si DRF valida esos campos como ForeignKey
    # antes de crear componentes/separadores, lanza:
    # "Tipo incorrecto. Se esperaba valor de clave primaria y se recibiÃ³ str."
    # Por eso aceptamos la estructura como JSON/lista de dicts y la resolvemos
    # manualmente en _replace_resultados().
    resultados = serializers.ListField(
        child=serializers.DictField(), required=False, allow_empty=True, write_only=True
    )

    class Meta:
        model = Prueba
        fields = [
            "id", "nombre_variable", "condicion", "acronimo", "unidad_medida",
            "unidad_catalogo", "condicion_catalogo", "metodo",
            "activo", "resultados",
        ]
        read_only_fields = ["id"]

    def validate_acronimo(self, value):
        value = value.strip()
        qs = Prueba.objects.filter(acronimo__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una prueba con este acrÃ³nimo.")
        return value

    def validate(self, attrs):

        # Los mÃ©todos reales vienen de MetodoEquipo.
        # Por ahora los submÃ©todos tÃ©cnicos no se validan contra MetodoEquipo
        # porque ese catÃ¡logo todavÃ­a no expone submÃ©todos.
        if "unidad_catalogo" in attrs:
            attrs["unidad_medida"] = attrs["unidad_catalogo"].simbolo if attrs["unidad_catalogo"] else None

        if "condicion_catalogo" in attrs:
            attrs["condicion"] = format_condition_label(attrs["condicion_catalogo"])

        return attrs

    def _replace_resultados(self, prueba, resultados_data):
        if resultados_data is None:
            return

        prueba.resultados.all().delete()

        for resultado_index, resultado_data in enumerate(resultados_data, start=1):
            divisiones_data = resultado_data.pop("divisiones", None)
            resultado_data.pop("temp_id", None)

            resultado = PruebaResultado.objects.create(
                prueba=prueba,
                nombre=resultado_data["nombre"],
                acronimo=resultado_data.get("acronimo"),
                descripcion=resultado_data.get("descripcion"),
                unidad_medida=resultado_data.get("unidad_medida") or prueba.unidad_medida,
                unidad_catalogo_id=resultado_data.get("unidad_catalogo") or prueba.unidad_catalogo_id,
                orden=resultado_data.get("orden") or resultado_index,
                activo=resultado_data.get("activo", True),
            )

            # Resultado simple: si no llegan divisiones, creamos una divisiÃ³n principal.
            if not divisiones_data:
                divisiones_data = [{
                    "nombre": None,
                    "es_principal": True,
                    "orden": 1,
                    "componentes": [{
                        "nombre": resultado.nombre,
                        "acronimo": resultado.acronimo,
                        "unidad_medida": prueba.unidad_medida,
                        "tipo_dato": "numerico",
                        "orden": 1,
                        "activo": True,
                    }],
                    "separadores": [],
                    "disposiciones": [],
                }]

            for division_index, division_data in enumerate(divisiones_data, start=1):
                componentes_data = division_data.pop("componentes", [])
                separadores_data = division_data.pop("separadores", [])
                disposiciones_data = division_data.pop("disposiciones", [])
                division_data.pop("temp_id", None)

                division = PruebaResultadoDivision.objects.create(
                    resultado=resultado,
                    nombre=division_data.get("nombre"),
                    es_principal=division_data.get("es_principal", False),
                    orden=division_data.get("orden") or division_index,
                    activo=division_data.get("activo", True),
                )

                componente_map = {}
                for componente_index, componente_data in enumerate(componentes_data, start=1):
                    temp_key = str(
                        componente_data.pop("temp_id", None)
                        or componente_data.get("id")
                        or componente_index
                    )
                    tipo_dato = componente_data.get("tipo_dato", "numerico")
                    tipo_dato = {
                        "escala_ordinal": "escala",
                        "opcion": "escala",
                        "texto": "comentario",
                    }.get(tipo_dato, tipo_dato)
                    componente = PruebaResultadoComponente.objects.create(
                        division=division,
                        nombre=componente_data["nombre"],
                        acronimo=componente_data.get("acronimo"),
                        tipo_dato=tipo_dato,
                        escala_comparacion_id=componente_data.get("escala_comparacion"),
                        opciones_resultado=componente_data.get("opciones_resultado"),
                        etiqueta_verdadero=componente_data.get("etiqueta_verdadero") or "Sí",
                        etiqueta_falso=componente_data.get("etiqueta_falso") or "No",
                        requiere_valor=componente_data.get("requiere_valor", True),
                        permite_observacion=componente_data.get("permite_observacion", True),
                        orden=componente_data.get("orden") or componente_index,
                        activo=componente_data.get("activo", True),
                    )
                    componente_map[temp_key] = componente

                separador_map = {}
                for separador_index, separador_data in enumerate(separadores_data, start=1):
                    temp_key = str(
                        separador_data.pop("temp_id", None)
                        or separador_data.get("id")
                        or separador_index
                    )
                    separador = PruebaResultadoSeparador.objects.create(
                        division=division,
                        simbolo=separador_data["simbolo"],
                        orden=separador_data.get("orden") or separador_index,
                        activo=separador_data.get("activo", True),
                    )
                    separador_map[temp_key] = separador

                for disposicion_index, disposicion_data in enumerate(disposiciones_data, start=1):
                    items_data = disposicion_data.pop("items", [])
                    disposicion_data.pop("temp_id", None)
                    disposicion = PruebaResultadoDisposicion.objects.create(
                        division=division,
                        nombre=disposicion_data.get("nombre") or "DisposiciÃ³n principal",
                        orden=disposicion_data.get("orden") or disposicion_index,
                        activo=disposicion_data.get("activo", True),
                    )

                    for item_index, item_data in enumerate(items_data, start=1):
                        tipo = item_data.get("tipo")
                        componente = None
                        separador = None

                        if tipo == "componente":
                            componente = componente_map.get(str(item_data.get("componente")))
                        if tipo == "separador":
                            separador = separador_map.get(str(item_data.get("separador")))

                        PruebaResultadoDisposicionItem.objects.create(
                            disposicion=disposicion,
                            tipo=tipo,
                            componente=componente,
                            separador=separador,
                            orden=item_data.get("orden") or item_index,
                        )

        # La estructura anidada se recrea, pero los límites se conservan por el
        # código estable de cada campo y se enlazan a los IDs recién creados.
        from apps.misc.api.services.limit_contract import reconcile_limit_contract
        reconcile_limit_contract(prueba)

    def create(self, validated_data):
        resultados_data = validated_data.pop("resultados", [])
        prueba = Prueba.objects.create(**validated_data)
        self._replace_resultados(prueba, resultados_data)
        return prueba

    def update(self, instance, validated_data):
        resultados_data = validated_data.pop("resultados", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self._replace_resultados(instance, resultados_data)
        return instance


# Compatibilidad temporal con mÃ³dulos viejos que todavÃ­a importan PruebaSerializer.
PruebaSerializer = PruebaDetailSerializer
