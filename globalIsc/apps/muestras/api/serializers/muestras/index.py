import json

from django.db import transaction
from rest_framework import serializers

from apps.muestras.api.models.muestras.index import HistorialMuestra, Muestra
from apps.users.api.models.index import User
from apps.users.api.data_scope import can_access_company
from apps.muestras.api.serializers.muestraAtributoTecnico.index import (
    MuestraAtributoTecnicoSerializer,
    replace_sample_attributes,
    validate_required_sample_attributes,
)
from apps.muestras.api.serializers.pruebasMuestra.index import PruebaMuestraSerializer
from apps.muestras.services.operational_audit import record_operational_event
from apps.activesTree.api.models.index import AsignacionPuntoMuestreo


class CreateMuestraSerializer(serializers.ModelSerializer):
    atributos_tecnicos = MuestraAtributoTecnicoSerializer(many=True, required=False)

    class Meta:
        model = Muestra
        fields = "__all__"
        extra_kwargs = {
            "usuario_registro": {"required": False},
            "id": {"read_only": True},
        }

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        lote = attrs.get("lote") or getattr(self.instance, "lote", None)
        equipo = attrs.get("referencia_equipo") or getattr(self.instance, "referencia_equipo", None)
        if user:
            if lote and not can_access_company(user, lote.cliente_empresa_id):
                raise serializers.ValidationError({"lote": "No tiene acceso a este lote."})
            if equipo and not can_access_company(user, equipo.empresa_id):
                raise serializers.ValidationError({"referencia_equipo": "No tiene acceso a esta máquina."})

        tipo_muestra = attrs.get("tipo_muestra") or getattr(self.instance, "tipo_muestra", None)
        attributes_were_sent = "atributos_tecnicos" in attrs
        sample_type_changed = self.instance is not None and "tipo_muestra" in attrs
        if self.instance is None or attributes_were_sent or sample_type_changed:
            validate_required_sample_attributes(tipo_muestra, attrs.get("atributos_tecnicos") or [])
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        atributos_data = validated_data.pop("atributos_tecnicos", [])
        request = self.context.get("request")
        if "usuario_registro" not in validated_data and request and request.user.is_authenticated:
            validated_data["usuario_registro"] = request.user
        muestra = super().create(validated_data)
        replace_sample_attributes(muestra, atributos_data)
        request = self.context.get("request")
        record_operational_event(
            actor=request.user if request and request.user.is_authenticated else None,
            action="muestra.creada",
            entity_type="muestra",
            entity_id=muestra.id,
            entity_label=muestra.id,
            muestra=muestra,
            detail="Muestra creada.",
            after=build_sample_snapshot(muestra),
        )
        return muestra

    @transaction.atomic
    def update(self, instance, validated_data):
        estado_anterior = build_sample_snapshot(instance)
        atributos_data = validated_data.pop("atributos_tecnicos", None)

        # A sampling point is part of a machine's technical context.  Leaving an
        # active assignment behind when the machine changes corrupts both the
        # current view and the trend history, so close it before saving the new
        # machine.  The assignment is retained as history; it is never deleted.
        machine_changed = (
            "referencia_equipo" in validated_data
            and getattr(validated_data["referencia_equipo"], "id", None) != instance.referencia_equipo_id
        )
        previous_point = None
        if machine_changed:
            active_assignment = (
                AsignacionPuntoMuestreo.objects.select_for_update()
                .filter(muestra=instance, activa=True)
                .select_related("punto_muestreo")
                .first()
            )
            if active_assignment:
                previous_point = active_assignment.punto_muestreo
                active_assignment.close()

        muestra = super().update(instance, validated_data)
        if atributos_data is not None:
            replace_sample_attributes(muestra, atributos_data)
        muestra.refresh_from_db()
        estado_nuevo = build_sample_snapshot(muestra)
        cambios = build_snapshot_changes(estado_anterior, estado_nuevo)
        if cambios:
            request = self.context.get("request")
            HistorialMuestra.objects.create(
                muestra=muestra,
                usuario=request.user if request and request.user.is_authenticated else None,
                cambios=cambios,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_nuevo,
            )
            request = self.context.get("request")
            record_operational_event(
                actor=request.user if request and request.user.is_authenticated else None,
                action="muestra.actualizada",
                entity_type="muestra",
                entity_id=muestra.id,
                entity_label=muestra.id,
                muestra=muestra,
                detail="Información de muestra actualizada.",
                before=estado_anterior,
                after=estado_nuevo,
                metadata={"campos_modificados": sorted(cambios)},
            )
        if previous_point:
            request = self.context.get("request")
            record_operational_event(
                actor=request.user if request and request.user.is_authenticated else None,
                action="muestra.punto_muestreo_desasignado",
                entity_type="muestra",
                entity_id=muestra.id,
                entity_label=muestra.id,
                muestra=muestra,
                maquina=muestra.referencia_equipo,
                detail="Punto de medida retirado al cambiar el equipo de la muestra.",
                before={"punto_muestreo": {"id": previous_point.id, "nombre": previous_point.nombre}},
                after={"punto_muestreo": None},
            )
        return muestra


def build_sample_snapshot(muestra):
    scalar_fields = (
        "tipo_muestra",
        "fecha_toma",
        "contacto_cliente",
        "equipo_placa",
        "periodo_servicio_aceite",
        "unidad_periodo_aceite",
        "periodo_servicio_equipo",
        "unidad_periodo_equipo",
        "observaciones",
        "campos_adicionales",
        "condicion",
        "fecha_envio",
        "referencia_marca",
    )
    snapshot = {}
    for field in scalar_fields:
        value = getattr(muestra, field, None)
        snapshot[field] = value.isoformat() if hasattr(value, "isoformat") else value
    equipo = muestra.referencia_equipo
    snapshot["referencia_equipo_id"] = (
        {
            "id": equipo.id,
            "nombre": equipo.nombre,
            "codigo": equipo.codigo_equipo,
        }
        if equipo
        else None
    )
    current_assignment = muestra.asignaciones_punto_muestreo.filter(activa=True).select_related("punto_muestreo").first()
    snapshot["punto_muestreo"] = (
        {"id": current_assignment.punto_muestreo_id, "nombre": current_assignment.punto_muestreo.nombre}
        if current_assignment
        else None
    )
    snapshot["atributos_tecnicos"] = [
        {
            "campo_tecnico": attribute.campo_tecnico_id,
            "catalogo": attribute.catalogo_id,
            "item": attribute.item_id,
            "desconocido": attribute.desconocido,
            "observacion": attribute.observacion,
        }
        for attribute in muestra.atributos_tecnicos.order_by("campo_tecnico_id", "catalogo_id", "id")
    ]
    return snapshot


def build_snapshot_changes(before, after):
    changes = {}
    for field in sorted(set(before) | set(after)):
        if before.get(field) != after.get(field):
            changes[field] = {
                "anterior": before.get(field),
                "nuevo": after.get(field),
            }
    return changes


class HistorialMuestraSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = HistorialMuestra
        fields = (
            "id",
            "accion",
            "cambios",
            "estado_anterior",
            "estado_nuevo",
            "usuario",
            "usuario_nombre",
            "creado_en",
        )

    def get_usuario_nombre(self, obj):
        if not obj.usuario:
            return "Sistema"
        return obj.usuario.get_full_name() or obj.usuario.email or str(obj.usuario_id)


class MuestraListSerializer(serializers.ModelSerializer):
    referencia_equipo_info = serializers.SerializerMethodField()
    referencia_equipo_nombre = serializers.SerializerMethodField()
    resultados = serializers.SerializerMethodField()
    pruebas_asignadas = serializers.SerializerMethodField()
    atributos_tecnicos = MuestraAtributoTecnicoSerializer(many=True, read_only=True)
    punto_muestreo = serializers.SerializerMethodField()

    class Meta:
        model = Muestra
        fields = "__all__"

    def get_referencia_equipo_info(self, obj):
        if not obj.referencia_equipo:
            return None
        empresa = obj.referencia_equipo.empresa
        return {
            "id": obj.referencia_equipo.id,
            "nombre": obj.referencia_equipo.nombre,
            "codigo_equipo": obj.referencia_equipo.codigo_equipo,
            "empresa": {"id": empresa.id, "nombre": empresa.nombre} if empresa else None,
        }

    def get_referencia_equipo_nombre(self, obj):
        return getattr(obj.referencia_equipo, "nombre", None)

    def get_punto_muestreo(self, obj):
        assignments = getattr(obj, 'asignaciones_punto_muestreo', None)
        if assignments is None:
            return None
        current = next((item for item in assignments.all() if item.activa), None)
        if not current:
            nombre = (obj.campos_adicionales or {}).get('punto_muestreo_manual')
            return {'id': None, 'nombre': nombre, 'manual': True} if nombre else None
        return {
            'id': current.punto_muestreo_id,
            'nombre': current.punto_muestreo.nombre,
            'maquina_id': current.punto_muestreo.maquina_id,
        }

    def get_resultados(self, obj):
        return [{"id": resultado.id} for resultado in obj.resultados.all()]

    def get_pruebas_asignadas(self, obj):
        data = []
        for prueba_muestra in obj.resultados.all():
            prueba = prueba_muestra.prueba
            prefetched_results = getattr(prueba_muestra, "_prefetched_objects_cache", {}).get("resultados")
            latest_result = max(
                list(prefetched_results or []),
                key=lambda item: ((item.fecha_actualizacion or item.fecha_registro or item.fecha_medicion), item.id),
                default=None,
            )
            payload = None
            if latest_result:
                try:
                    payload = json.loads(latest_result.resultado)
                except (TypeError, ValueError):
                    payload = None
            data.append({
                "id": prueba_muestra.id,
                "valor": prueba_muestra.valor,
                "unidad": prueba_muestra.unidad,
                "estatus": prueba_muestra.estatus,
                "completada": prueba_muestra.completada,
                "aplicar_limites": prueba_muestra.aplicar_limites,
                "estado_limite": prueba_muestra.estado_limite,
                "evaluacion_limite": prueba_muestra.evaluacion_limite,
                "configuracion_resultados": prueba_muestra.configuracion_resultados or {},
                "resultado_payload": payload,
                "fecha_medicion": latest_result.fecha_medicion if latest_result else prueba_muestra.fecha_medicion,
                "prueba": {
                    "id": prueba.id,
                    "nombre_variable": prueba.nombre_variable,
                    "acronimo": prueba.acronimo,
                    "unidad_medida": prueba.unidad_medida,
                    "metodo": prueba.metodo_id,
                    "metodo_nombre": prueba.metodo.nombre if prueba.metodo_id else None,
                    "metodo_codigo": prueba.metodo.codigo if prueba.metodo_id else None,
                    "equipo": prueba.equipo,
                    "condicion": prueba.condicion,
                },
            })
        return data


class MuestraSerializer(MuestraListSerializer):
    resultados = PruebaMuestraSerializer(many=True, read_only=True)

    def get_referencia_equipo_info(self, obj):
        if not obj.referencia_equipo:
            return None
        empresa = obj.referencia_equipo.empresa
        return {
            "id": obj.referencia_equipo.id,
            "nombre": obj.referencia_equipo.nombre,
            "codigo_equipo": obj.referencia_equipo.codigo_equipo,
            "numero_serie": obj.referencia_equipo.numero_serie,
            "componente": obj.referencia_equipo.componente,
            "tipoAceite": obj.referencia_equipo.tipoAceite,
            "frecuenciaCambio": obj.referencia_equipo.frecuenciaCambio,
            "frecuenciaAnalisis": obj.referencia_equipo.frecuenciaAnalisis,
            "empresa_info": {"id": empresa.id, "nombre": empresa.nombre} if empresa else None,
        }
