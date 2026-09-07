from rest_framework import serializers
from django.db import transaction
from django.db.models import Q

from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.activesTree.api.models.machines.index import Maquina
from apps.users.api.models.index import User
from apps.muestras.api.serializers.muestras.index import MuestraListSerializer, MuestraSerializer
from apps.misc.api.serializers.tipoGestionMuestra.index import TipoGestionMuestraSerializer
from apps.muestras.api.serializers.muestraAtributoTecnico.index import (
    MuestraAtributoTecnicoSerializer,
    replace_sample_attributes,
)
from apps.muestras.api.services.workflow import capabilities_for_batch

class MuestraLoteCreateSerializer(serializers.ModelSerializer):
    atributos_tecnicos = MuestraAtributoTecnicoSerializer(many=True, required=False)
    class Meta:
        model = Muestra
        fields = [
            "id",
            "fecha_toma",
            "fecha_envio",
            "tipo_muestra",
            "condicion",
            "contacto_cliente",
            "equipo_placa",
            "referencia_equipo",
            "periodo_servicio_aceite",
            "unidad_periodo_aceite",
            "periodo_servicio_equipo",
            "unidad_periodo_equipo",
            "referencia_marca",
            "observaciones",
            "campos_adicionales",
            "atributos_tecnicos",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        tipo_muestra = attrs.get("tipo_muestra")
        condicion = attrs.get("condicion")

        referencia_equipo = attrs.get("referencia_equipo")
        equipo_placa = attrs.get("equipo_placa")

        if condicion == "usada" and not referencia_equipo and not equipo_placa:
            raise serializers.ValidationError({
                "referencia_equipo": "Una muestra usada debe tener equipo asociado o placa manual."
            })

        if tipo_muestra == "aceite":
            # Para aceite puedes validar nivel_desempeno si quieres hacerlo obligatorio.
            pass

        if tipo_muestra == "grasa":
            # Para grasa puedes validar NLGI si luego lo quieres obligatorio.
            pass

        return attrs


class LoteMuestrasListSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.SerializerMethodField()
    total_muestras = serializers.SerializerMethodField()
    progreso = serializers.SerializerMethodField()
    progreso_pruebas = serializers.SerializerMethodField()
    tipos_muestras = serializers.SerializerMethodField()
    acciones_disponibles = serializers.SerializerMethodField()
    muestras_coincidentes = serializers.SerializerMethodField()
    tipo_gestion_info = TipoGestionMuestraSerializer(
    source="tipo_gestion",
    read_only=True
)
    class Meta:
        model = LoteMuestras
        fields = [
            "id",
            "tipo_cliente",
            "cliente_empresa",
            "cliente_ocasional_nombre",
            "cliente_nombre",
            "contacto_nombre",
            "contacto_telefono",
            "contacto_email",
            "fecha_envio",
            "fecha_recepcion",
            "tipo_gestion",
            "estado",
            "observaciones",
            "motivo_cancelacion",
            "fecha_cancelacion",
            "cancelado_por",
            "usuario_registro",
            "fecha_registro",
            "fecha_actualizacion",
            "total_muestras",
            "progreso",
            "progreso_pruebas",
            "tipos_muestras",
            "acciones_disponibles",
            "muestras_coincidentes",
            "tipo_gestion",
            "tipo_gestion_info",
        ]

    def get_acciones_disponibles(self, obj):
        return capabilities_for_batch(obj).to_dict()

    def get_muestras_coincidentes(self, obj):
        return getattr(obj, 'muestras_coincidentes_db', None)

    def get_cliente_nombre(self, obj):
        if obj.tipo_cliente == "registrado" and obj.cliente_empresa:
            return getattr(obj.cliente_empresa, "nombre", str(obj.cliente_empresa))

        return obj.cliente_ocasional_nombre

    def get_total_muestras(self, obj):
        return getattr(obj, "total_muestras_db", obj.total_muestras)

    def get_progreso(self, obj):
        total = getattr(obj, "muestras_activas_db", None)
        procesadas = getattr(obj, "muestras_resultado_ingresado_db", None)

        if total is not None and procesadas is not None:
            porcentaje = round((procesadas / total) * 100) if total else 0
            return {
                "total": total,
                "procesadas": procesadas,
                "porcentaje": porcentaje,
                "label": f"{procesadas}/{total} procesadas",
            }

        return obj.progreso

    def get_progreso_pruebas(self, obj):
        total = getattr(obj, "pruebas_asignadas_db", None)
        completadas = getattr(obj, "pruebas_completadas_db", None)
        revisadas = getattr(obj, "pruebas_revisadas_db", None)
        if total is None:
            muestras = getattr(obj, "muestras", None)
            if hasattr(muestras, "all"):
                pruebas = []
                for muestra in muestras.all():
                    if muestra.estado_operativo != "activa":
                        continue
                    pruebas.extend(list(getattr(muestra, "resultados", []).all()))
                total = len([item for item in pruebas if item.estado_asignacion == "confirmada"])
                completadas = len([item for item in pruebas if item.estado_asignacion == "confirmada" and item.completada])
                revisadas = len([item for item in pruebas if item.estado_asignacion == "confirmada" and item.is_revisada])
            else:
                total = completadas = revisadas = 0
        return {
            "asignadas": total or 0,
            "completadas": completadas or 0,
            "revisadas": revisadas or 0,
        }

    def get_tipos_muestras(self, obj):
        aceite = getattr(obj, "muestras_aceite_db", None)
        grasa = getattr(obj, "muestras_grasa_db", None)

        if aceite is not None and grasa is not None:
            if aceite and grasa:
                return "Aceite / Grasa"
            if aceite:
                return "Aceite"
            if grasa:
                return "Grasa"
            return "-"

        tipos = set(obj.muestras.values_list("tipo_muestra", flat=True))

        if "aceite" in tipos and "grasa" in tipos:
            return "Aceite / Grasa"

        if "aceite" in tipos:
            return "Aceite"

        if "grasa" in tipos:
            return "Grasa"

        return "-"


class LoteMuestrasDetailSerializer(LoteMuestrasListSerializer):
    muestras = MuestraListSerializer(many=True, read_only=True)

    class Meta(LoteMuestrasListSerializer.Meta):
        fields = LoteMuestrasListSerializer.Meta.fields + [
            "muestras",
        ]


class LoteMuestrasCreateSerializer(serializers.ModelSerializer):
    muestras = MuestraLoteCreateSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = LoteMuestras
        fields = [
            "id",
            "tipo_cliente",
            "cliente_empresa",
            "cliente_ocasional_nombre",
            "contacto_nombre",
            "contacto_telefono",
            "contacto_email",
            "fecha_envio",
            "fecha_recepcion",
            "tipo_gestion",
            "estado",
            "observaciones",
            "usuario_registro",
            "muestras",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "usuario_registro": {"required": False},
        }

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        tipo_cliente = attrs.get("tipo_cliente")

        if user and user.is_authenticated and not (user.is_superuser or user.role == User.Role.GLOBAL):
            attrs["tipo_cliente"] = "registrado"
            attrs["cliente_empresa"] = user.empresa
            attrs["cliente_ocasional_nombre"] = None
            tipo_cliente = "registrado"

        if tipo_cliente == "registrado" and not attrs.get("cliente_empresa"):
            raise serializers.ValidationError({
                "cliente_empresa": "Debe seleccionar una empresa registrada."
            })

        if tipo_cliente == "ocasional" and not attrs.get("cliente_ocasional_nombre"):
            raise serializers.ValidationError({
                "cliente_ocasional_nombre": "Debe ingresar el nombre del cliente ocasional."
            })

        return attrs

    def _resolve_manual_machine(self, lote, muestra_data):
        if muestra_data.get("referencia_equipo") or not muestra_data.get("equipo_placa"):
            return muestra_data
        empresa = lote.cliente_empresa
        placa = str(muestra_data.get("equipo_placa") or "").strip()
        if not empresa or not placa:
            return muestra_data

        machine = (
            Maquina.objects
            .filter(empresa=empresa)
            .filter(Q(codigo_equipo__iexact=placa) | Q(nombre__iexact=placa) | Q(numero_serie__iexact=placa))
            .first()
        )
        if not machine:
            machine = Maquina.objects.create(
                empresa=empresa,
                nombre=placa,
                codigo_equipo=placa,
            )
        muestra_data["referencia_equipo"] = machine
        return muestra_data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        muestras_data = validated_data.pop("muestras", [])

        if request and request.user and request.user.is_authenticated:
            validated_data["usuario_registro"] = request.user

        lote = LoteMuestras.objects.create(**validated_data)

        for muestra_data in muestras_data:
            atributos_data = muestra_data.pop("atributos_tecnicos", None)
            muestra_data.pop("fecha_envio", None)
            muestra_data.pop("contacto_cliente", None)
            muestra_data.pop("usuario_registro", None)
            muestra_data.pop("lote", None)
            muestra_data = self._resolve_manual_machine(lote, muestra_data)

            muestra = Muestra.objects.create(
                lote=lote,
                fecha_envio=lote.fecha_envio,
                contacto_cliente=lote.contacto_nombre,
                usuario_registro=lote.usuario_registro,
                **muestra_data,
            )
            if atributos_data is not None:
                replace_sample_attributes(muestra, atributos_data)

        lote.recalcular_estado()

        return lote

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop("muestras", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        instance.recalcular_estado()

        return instance
class AddMuestrasToLoteSerializer(serializers.Serializer):
    muestras = MuestraLoteCreateSerializer(many=True)

    def validate_muestras(self, value):
        if not value:
            raise serializers.ValidationError(
                "Debe enviar al menos una muestra."
            )

        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        lote = self.context.get("lote")

        muestras_data = validated_data.get("muestras", [])

        created_muestras = []

        for muestra_data in muestras_data:
            atributos_data = muestra_data.pop("atributos_tecnicos", None)
            muestra_data.pop("fecha_envio", None)
            muestra_data.pop("contacto_cliente", None)
            muestra_data.pop("usuario_registro", None)
            muestra_data.pop("lote", None)
            if not muestra_data.get("referencia_equipo") and muestra_data.get("equipo_placa") and lote.cliente_empresa_id:
                placa = str(muestra_data.get("equipo_placa") or "").strip()
                machine = (
                    Maquina.objects
                    .filter(empresa=lote.cliente_empresa)
                    .filter(Q(codigo_equipo__iexact=placa) | Q(nombre__iexact=placa) | Q(numero_serie__iexact=placa))
                    .first()
                )
                if not machine:
                    machine = Maquina.objects.create(
                        empresa=lote.cliente_empresa,
                        nombre=placa,
                        codigo_equipo=placa,
                    )
                muestra_data["referencia_equipo"] = machine

            muestra = Muestra.objects.create(
                lote=lote,
                fecha_envio=lote.fecha_envio,
                contacto_cliente=lote.contacto_nombre,
                usuario_registro=request.user if request and request.user.is_authenticated else lote.usuario_registro,
                **muestra_data,
            )
            if atributos_data is not None:
                replace_sample_attributes(muestra, atributos_data)

            created_muestras.append(muestra)

        lote.recalcular_estado()

        return created_muestras
