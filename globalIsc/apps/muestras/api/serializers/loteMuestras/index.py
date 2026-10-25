from rest_framework import serializers
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.activesTree.api.models.machines.index import Maquina
from apps.activesTree.api.models.index import AsignacionPuntoMuestreo, PuntoMuestreo, Lubricante
from apps.activesTree.services import ensure_machine_tree_node
from apps.users.api.models.index import User
from apps.users.api.data_scope import can_access_company, effective_data_scope
from apps.users.api.services import is_global_user
from apps.muestras.api.serializers.muestras.index import MuestraListSerializer, MuestraSerializer
from apps.misc.api.serializers.tipoGestionMuestra.index import TipoGestionMuestraSerializer
from apps.muestras.api.serializers.muestraAtributoTecnico.index import (
    MuestraAtributoTecnicoSerializer,
    replace_sample_attributes,
)
from apps.muestras.api.services.workflow import capabilities_for_batch
from apps.muestras.services.operational_audit import record_operational_event


def _record_sample_created_from_lot(muestra, actor):
    record_operational_event(
        actor=actor,
        action="muestra.creada",
        entity_type="muestra",
        entity_id=muestra.id,
        entity_label=muestra.id,
        muestra=muestra,
        detail="Muestra creada dentro del lote.",
        after={
            "tipo_muestra": muestra.tipo_muestra,
            "condicion": muestra.condicion,
            "fecha_toma": muestra.fecha_toma.isoformat() if muestra.fecha_toma else None,
            "referencia_equipo": muestra.referencia_equipo_id,
            "referencia_marca": muestra.referencia_marca or "",
        },
    )


def _add_business_days(start_date, days):
    """Add working days (Monday-Friday) without changing the stored sample."""
    current = start_date
    remaining = max(0, int(days or 0))
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _business_days_remaining(today, due_date):
    if due_date == today:
        return 0
    direction = 1 if due_date > today else -1
    cursor = today
    total = 0
    while cursor != due_date:
        cursor += timedelta(days=direction)
        if cursor.weekday() < 5:
            total += direction
    return total


class LoteMuestraWorkspaceSerializer(serializers.ModelSerializer):
    """Lean sample projection used by the expandable batch workspace."""

    equipo = serializers.SerializerMethodField()
    punto_muestreo = serializers.SerializerMethodField()
    estado_flujo = serializers.SerializerMethodField()
    plazo_entrega = serializers.SerializerMethodField()

    class Meta:
        model = Muestra
        fields = [
            "id",
            "tipo_muestra",
            "condicion",
            "fecha_toma",
            "estado_operativo",
            "is_ingresado",
            "is_resultado_ingresado",
            "is_revisado",
            "equipo",
            "punto_muestreo",
            "estado_flujo",
            "plazo_entrega",
        ]

    def get_equipo(self, obj):
        machine = obj.referencia_equipo
        if machine:
            return {
                "id": machine.id,
                "nombre": machine.nombre,
                "codigo": machine.codigo_equipo,
                "manual": False,
                "label": machine.codigo_equipo or machine.nombre,
            }
        if obj.equipo_placa:
            return {"id": None, "nombre": obj.equipo_placa, "codigo": None, "manual": True, "label": obj.equipo_placa}
        return None

    def get_punto_muestreo(self, obj):
        assignments = obj.asignaciones_punto_muestreo.all()
        current = next((item for item in assignments if item.activa), None)
        if not current:
            nombre = (obj.campos_adicionales or {}).get('punto_muestreo_manual')
            return {"id": None, "nombre": nombre, "manual": True} if nombre else None
        return {"id": current.punto_muestreo_id, "nombre": current.punto_muestreo.nombre}

    def get_estado_flujo(self, obj):
        lote = obj.lote
        if obj.estado_operativo != "activa":
            return {"code": "invalidada", "label": "Invalidada"}
        if obj.reportes.filter(
            visible_cliente=True,
            fecha_aprobacion__isnull=False,
            usuario_aprobacion__isnull=False,
        ).exclude(estatus="anulado").exists():
            return {"code": "reportada", "label": "Reportada"}
        if obj.is_revisado:
            return {"code": "revisada", "label": "Revisada"}
        if obj.is_resultado_ingresado:
            return {"code": "resultados_completos", "label": "Resultados completos"}
        if obj.is_ingresado:
            return {"code": "en_laboratorio", "label": "En laboratorio"}
        if lote and lote.estado == "borrador":
            return {"code": "borrador", "label": "Borrador"}
        return {"code": "registrada", "label": "Registrada"}

    def get_plazo_entrega(self, obj):
        # SLA is operational information for Global Oil.  A company user sees
        # the actual workflow state, never its internal deadline/countdown.
        request = self.context.get("request")
        if request and not is_global_user(request.user):
            return {"configured": False, "hidden": True}
        lote = obj.lote
        management_type = getattr(lote, "tipo_gestion", None)
        if not lote or not management_type:
            return {"configured": False, "label": "Sin plazo configurado"}

        business_days = int(management_type.dias_habiles or 0)
        calendar_days = int(management_type.dias_calendario or 0)
        if business_days <= 0 and calendar_days <= 0:
            return {"configured": False, "label": "Sin plazo configurado"}

        uses_business_days = business_days > 0
        total_days = business_days if uses_business_days else calendar_days
        start_date = lote.fecha_recepcion
        if not start_date:
            return {
                "configured": True,
                "waiting_reception": True,
                "basis": "habiles" if uses_business_days else "calendario",
                "total_days": total_days,
                "start_date": None,
                "due_date": None,
                "remaining_days": None,
                "progress_percent": 0,
                "status": "pendiente_recepcion",
                "label": "SLA inicia al recibir en laboratorio",
            }

        due_date = _add_business_days(start_date, total_days) if uses_business_days else start_date + timedelta(days=total_days)
        today = timezone.localdate()
        remaining = _business_days_remaining(today, due_date) if uses_business_days else (due_date - today).days
        elapsed = total_days - remaining
        progress = min(100, max(0, round((elapsed / total_days) * 100))) if total_days else 0

        if lote.estado == "reportado":
            status_code, label, progress = "entregada", "Informe reportado", 100
        elif remaining < 0:
            status_code, label = "vencida", f"Vencida hace {abs(remaining)} día(s)"
        elif remaining == 0:
            status_code, label = "vence_hoy", "Vence hoy"
        else:
            suffix = "hábil(es)" if uses_business_days else "calendario(s)"
            status_code, label = "en_plazo", f"{remaining} día(s) {suffix} restantes"

        return {
            "configured": True,
            "basis": "habiles" if uses_business_days else "calendario",
            "total_days": total_days,
            "start_date": start_date.isoformat(),
            "due_date": due_date.isoformat(),
            "remaining_days": remaining,
            "progress_percent": progress,
            "status": status_code,
            "label": label,
        }

class MuestraLoteCreateSerializer(serializers.ModelSerializer):
    atributos_tecnicos = MuestraAtributoTecnicoSerializer(many=True, required=False)
    punto_muestreo_manual = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, write_only=True, max_length=150
    )
    punto_muestreo = serializers.PrimaryKeyRelatedField(
        # The reception form sends an explicit null when the operator uses a
        # manual equipment identifier.  `required=False` only accepts an
        # omitted key; `allow_null=True` lets validation decide whether a
        # manual identifier is sufficient for a used sample.
        queryset=PuntoMuestreo.objects.filter(activo=True),
        required=False,
        allow_null=True,
        write_only=True,
    )
    lubricante_catalogo = serializers.PrimaryKeyRelatedField(
        queryset=Lubricante.objects.filter(activo=True), required=False, allow_null=True, write_only=True
    )
    lubricante_nuevo = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True, max_length=150)
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
            "punto_muestreo",
            "punto_muestreo_manual",
            "lubricante_catalogo",
            "lubricante_nuevo",
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
        punto_muestreo = attrs.get("punto_muestreo")
        punto_muestreo_manual = (attrs.get("punto_muestreo_manual") or "").strip()
        lubricante_catalogo = attrs.get("lubricante_catalogo")
        equipo_placa = attrs.get("equipo_placa")

        if punto_muestreo:
            if punto_muestreo_manual:
                raise serializers.ValidationError({
                    "punto_muestreo_manual": "Use un punto registrado o uno manual, no ambos."
                })
            if referencia_equipo and referencia_equipo.pk != punto_muestreo.maquina_id:
                raise serializers.ValidationError({"punto_muestreo": "El punto no pertenece a la máquina indicada."})
            attrs["referencia_equipo"] = punto_muestreo.maquina
            attrs["equipo_placa"] = None
            referencia_equipo = punto_muestreo.maquina

        if condicion == "usada" and not punto_muestreo and not equipo_placa:
            raise serializers.ValidationError({
                "punto_muestreo": "Una muestra usada debe seleccionar un punto de medida o usar identificación manual."
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
    equipo_resumen = serializers.SerializerMethodField()
    punto_muestreo_resumen = serializers.SerializerMethodField()
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
            "equipo_resumen",
            "punto_muestreo_resumen",
            "tipo_gestion",
            "tipo_gestion_info",
        ]

    def get_acciones_disponibles(self, obj):
        return capabilities_for_batch(obj).to_dict()

    def get_muestras_coincidentes(self, obj):
        return getattr(obj, 'muestras_coincidentes_db', None)

    def get_equipo_resumen(self, obj):
        names = []
        for muestra in obj.muestras.all():
            equipo = getattr(muestra, "referencia_equipo", None)
            label = getattr(equipo, "nombre", None) or getattr(equipo, "codigo_equipo", None) or muestra.equipo_placa
            if label and label not in names:
                names.append(label)
        return " · ".join(names[:3]) or "Sin equipo"

    def get_punto_muestreo_resumen(self, obj):
        names = []
        for muestra in obj.muestras.all():
            for assignment in muestra.asignaciones_punto_muestreo.all():
                if assignment.activa and assignment.punto_muestreo.nombre not in names:
                    names.append(assignment.punto_muestreo.nombre)
        return " · ".join(names[:3]) or "Sin punto"

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

        if user and user.is_authenticated and effective_data_scope(user) == "OWN_COMPANY":
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

        empresa = attrs.get("cliente_empresa")
        if empresa and user and user.is_authenticated and not can_access_company(user, empresa.id):
            raise serializers.ValidationError({"cliente_empresa": "No tiene acceso a esta empresa."})
        for muestra in attrs.get("muestras") or []:
            point = muestra.get("punto_muestreo")
            if point and empresa and point.maquina.empresa_id != empresa.id:
                raise serializers.ValidationError({"muestras": "El punto de medida no pertenece a la empresa del lote."})

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
        ensure_machine_tree_node(machine)
        muestra_data["referencia_equipo"] = machine
        return muestra_data

    def _resolve_manual_sampling_point(self, muestra, point_name, actor):
        """Create or reuse a point typed during reception for a manual asset.

        A manual point becomes an ordinary active tree point once its manual
        machine exists. This preserves the sample's trend and makes the asset
        available for later maintenance in the Machines module.
        """
        point_name = str(point_name or "").strip()
        if not point_name or not muestra.referencia_equipo_id:
            return None
        point, _ = PuntoMuestreo.objects.get_or_create(
            maquina=muestra.referencia_equipo,
            nombre=point_name,
            activo=True,
            defaults={
                "descripcion": "Punto de medida creado desde el ingreso manual de muestras.",
                "creado_por": actor,
            },
        )
        return point

    @staticmethod
    def _assign_sampling_point(muestra, punto_muestreo, actor, origen="lote"):
        if not punto_muestreo:
            return
        AsignacionPuntoMuestreo.objects.create(
            muestra=muestra,
            punto_muestreo=punto_muestreo,
            origen=origen,
            asignado_por=actor,
        )

    def _resolve_lubricant(self, lote, muestra_data):
        """A new name from reception becomes reusable, without altering any point."""
        catalogo = muestra_data.pop('lubricante_catalogo', None)
        nuevo = (muestra_data.pop('lubricante_nuevo', None) or '').strip()
        if not catalogo:
            campos = muestra_data.get('campos_adicionales') or {}
            fabricante = (campos.get('fabricante') or '').strip() or 'Sin fabricante'
            referencia = (muestra_data.get('referencia_marca') or nuevo or '').strip()
            if referencia:
                catalogo, _ = Lubricante.objects.get_or_create(
                    fabricante=fabricante,
                    referencia=referencia,
                    defaults={'nombre': f'{fabricante} {referencia}'},
                )
        if catalogo:
            muestra_data['referencia_marca'] = catalogo.referencia or catalogo.nombre
            campos = muestra_data.get('campos_adicionales') or {}
            if catalogo.fabricante:
                campos['fabricante'] = catalogo.fabricante
            campos['lubricante_catalogo_id'] = catalogo.id
            campos['lubricante_nombre'] = catalogo.nombre
            muestra_data['campos_adicionales'] = campos
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
            punto_muestreo = muestra_data.pop("punto_muestreo", None)
            punto_muestreo_manual = muestra_data.pop("punto_muestreo_manual", None)
            if punto_muestreo_manual:
                campos = dict(muestra_data.get("campos_adicionales") or {})
                campos["punto_muestreo_manual"] = punto_muestreo_manual
                muestra_data["campos_adicionales"] = campos
            muestra_data.pop("fecha_envio", None)
            muestra_data.pop("contacto_cliente", None)
            muestra_data.pop("usuario_registro", None)
            muestra_data.pop("lote", None)
            muestra_data = self._resolve_manual_machine(lote, muestra_data)
            muestra_data = self._resolve_lubricant(lote, muestra_data)

            muestra = Muestra.objects.create(
                lote=lote,
                fecha_envio=lote.fecha_envio,
                contacto_cliente=lote.contacto_nombre,
                usuario_registro=lote.usuario_registro,
                **muestra_data,
            )
            if atributos_data is not None:
                replace_sample_attributes(muestra, atributos_data)
            punto_muestreo = punto_muestreo or self._resolve_manual_sampling_point(
                muestra, punto_muestreo_manual, lote.usuario_registro
            )
            self._assign_sampling_point(muestra, punto_muestreo, lote.usuario_registro)
            _record_sample_created_from_lot(muestra, lote.usuario_registro)

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
            punto_muestreo = muestra_data.pop("punto_muestreo", None)
            punto_muestreo_manual = muestra_data.pop("punto_muestreo_manual", None)
            if punto_muestreo_manual:
                campos = dict(muestra_data.get("campos_adicionales") or {})
                campos["punto_muestreo_manual"] = punto_muestreo_manual
                muestra_data["campos_adicionales"] = campos
            muestra_data.pop("fecha_envio", None)
            muestra_data.pop("contacto_cliente", None)
            muestra_data.pop("usuario_registro", None)
            muestra_data.pop("lote", None)
            resolver = LoteMuestrasCreateSerializer()
            muestra_data = resolver._resolve_manual_machine(lote, muestra_data)
            muestra_data = resolver._resolve_lubricant(lote, muestra_data)

            muestra = Muestra.objects.create(
                lote=lote,
                fecha_envio=lote.fecha_envio,
                contacto_cliente=lote.contacto_nombre,
                usuario_registro=request.user if request and request.user.is_authenticated else lote.usuario_registro,
                **muestra_data,
            )
            if atributos_data is not None:
                replace_sample_attributes(muestra, atributos_data)
            actor = request.user if request and request.user.is_authenticated else lote.usuario_registro
            punto_muestreo = punto_muestreo or LoteMuestrasCreateSerializer()._resolve_manual_sampling_point(
                muestra, punto_muestreo_manual, actor
            )
            LoteMuestrasCreateSerializer._assign_sampling_point(muestra, punto_muestreo, actor)

            _record_sample_created_from_lot(
                muestra,
                request.user if request and request.user.is_authenticated else lote.usuario_registro,
            )

            created_muestras.append(muestra)

        lote.recalcular_estado()

        return created_muestras
