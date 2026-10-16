"""Carga un recorrido demostrativo, identificable y repetible para tendencias."""

import json

from datetime import datetime

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.activesTree.api.models.index import AsignacionPuntoMuestreo, PuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.pruebas.index import Prueba
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.reporte.api.models.index import Reporte
from apps.resultado.api.models.index import Resultado
from apps.users.api.models.index import User


DEMO_PREFIX = "DEMO-TREND"
TEST_CODES = ("INDVISC", "OXID", "NTR", "ESPDES", "AGUA")


def result_payload(fields, values):
    return {
        "fields": [
            {"key": key, "label": label, "componente_nombre": label, "unidad": unit}
            for key, label, unit in fields
        ],
        "values": [
            {"key": key, "value": str(value), "value_label": str(value), "observacion": "Dato demostrativo"}
            for key, value in values.items()
        ],
    }


class Command(BaseCommand):
    help = "Crea datos sintéticos de tendencia por punto de medición y sus informes de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="ID de la empresa para los datos demo. Usa Mineros S.A por defecto.")
        parser.add_argument("--months", type=int, default=6, help="Número de meses sintéticos (2 a 12).")

    def handle(self, *args, **options):
        months = max(2, min(options["months"], 12))
        company = Empresa.objects.filter(pk=options.get("company")).first() if options.get("company") else None
        company = company or Empresa.objects.filter(nombre__iexact="Mineros S.A").first() or Empresa.objects.first()
        operator = User.objects.filter(role=User.Role.GLOBAL).first() or User.objects.first()
        management_type = apps.get_model("misc", "TipoGestionMuestra").objects.first()
        tests = {item.acronimo: item for item in Prueba.objects.filter(acronimo__in=TEST_CODES)}

        if not company or not operator or not management_type:
            raise CommandError("Se requiere al menos una empresa, usuario y tipo de gestión para crear la demostración.")
        missing = [code for code in TEST_CODES if code not in tests]
        if missing:
            raise CommandError("Faltan pruebas para la demostración: " + ", ".join(missing))

        created = {"lotes": 0, "muestras": 0, "resultados": 0, "reportes": 0}
        with transaction.atomic():
            machine, _ = Maquina.objects.get_or_create(
                empresa=company,
                codigo_equipo="DEMO-DRAGA-05",
                defaults={
                    "nombre": "DEMO - DRAGA CUCHARA 05",
                    "descripcion": "Equipo demostrativo para tendencias. No corresponde a operación real.",
                    "tipoAceite": "Aceite de engranajes ISO VG 460",
                    "numero_serie": "DEMO-2026-05",
                    "activo": True,
                },
            )
            points = [
                PuntoMuestreo.objects.get_or_create(
                    maquina=machine,
                    nombre="Reductor transmisión principal",
                    defaults={"codigo": "DEMO-RED-PP", "descripcion": "Circuito de engranajes - demostración", "lubricante": "Gear Oil ISO VG 460", "activo": True},
                )[0],
                PuntoMuestreo.objects.get_or_create(
                    maquina=machine,
                    nombre="Sistema hidráulico de cucharas",
                    defaults={"codigo": "DEMO-HYD-CUCH", "descripcion": "Circuito hidráulico - demostración", "lubricante": "Hydraulic Oil ISO VG 68", "activo": True},
                )[0],
            ]

            for month_index in range(months):
                month = month_index + 1
                date = timezone.make_aware(datetime(2026, month, min(6 + month_index, 25), 10, 0))
                lot_id = f"{DEMO_PREFIX}-{month:02d}"
                lote, was_created = LoteMuestras.objects.get_or_create(
                    id=lot_id,
                    defaults={
                        "tipo_cliente": "registrado",
                        "cliente_empresa": company,
                        "contacto_nombre": "Demostración técnica",
                        "contacto_email": "demo@globaloil.local",
                        "fecha_envio": date.date(),
                        "fecha_recepcion": date.date(),
                        "tipo_gestion": management_type,
                        "estado": "reportado",
                        "observaciones": "Lote sintético para demostrar tendencias por punto de medición. No usar para decisiones operacionales.",
                        "usuario_registro": operator,
                    },
                )
                created["lotes"] += int(was_created)

                for point_index, point in enumerate(points):
                    sample_id = f"MD{month:02d}{point_index + 1:02d}26"
                    sample, was_created = Muestra.objects.get_or_create(
                        id=sample_id,
                        defaults={
                            "lote": lote,
                            "fecha_toma": date,
                            "referencia_equipo": machine,
                            "equipo_placa": machine.codigo_equipo,
                            "periodo_servicio_aceite": 900 + month_index * 180,
                            "unidad_periodo_aceite": "horas",
                            "periodo_servicio_equipo": 12400 + month_index * 220,
                            "unidad_periodo_equipo": "horas",
                            "tipo_muestra": "aceite",
                            "condicion": "usada",
                            "observaciones": "Muestra sintética de demostración. No usar como evidencia de laboratorio.",
                            "usuario_registro": operator,
                            "is_ingresado": True,
                            "is_resultado_ingresado": True,
                            "is_revisado": True,
                        },
                    )
                    created["muestras"] += int(was_created)
                    AsignacionPuntoMuestreo.objects.get_or_create(
                        muestra=sample,
                        activa=True,
                        defaults={"punto_muestreo": point, "origen": "manual", "asignado_por": operator},
                    )

                    is_reducer = point_index == 0
                    measurements = {
                        "INDVISC": [("visc_40", "Viscosidad cinemática 40 °C", "cSt")],
                        "OXID": [("oxid", "Oxidación", "Abs/0.1 mm")],
                        "NTR": [("nitr", "Nitración", "Abs/0.1 mm")],
                        "ESPDES": [("fe", "Hierro", "ppm"), ("cu", "Cobre", "ppm"), ("si", "Silicio", "ppm")],
                        "AGUA": [("agua", "Contenido de agua", "%")],
                    }
                    values_by_test = {
                        "INDVISC": {"visc_40": round((452 if is_reducer else 66) + month_index * (2.1 if is_reducer else 0.45), 2)},
                        "OXID": {"oxid": round((0.035 if is_reducer else 0.018) + month_index * 0.008, 3)},
                        "NTR": {"nitr": round((0.010 if is_reducer else 0.006) + month_index * 0.004, 3)},
                        "ESPDES": {
                            "fe": (18 if is_reducer else 7) + month_index * (12 if is_reducer else 3),
                            "cu": (3 if is_reducer else 1) + month_index * (2 if is_reducer else 0.6),
                            "si": (8 if is_reducer else 5) + month_index * (3 if is_reducer else 1),
                        },
                        "AGUA": {"agua": round((0.03 if is_reducer else 0.01) + month_index * 0.012, 3)},
                    }
                    for code, fields in measurements.items():
                        assignment, _ = PruebaMuestra.objects.get_or_create(
                            muestra=sample,
                            prueba=tests[code],
                            defaults={
                                "usuario_solicitud": operator,
                                "usuario_medicion": operator,
                                "usuario_revision": operator,
                                "fecha_medicion": date,
                                "fecha_revision": date,
                                "valor": " / ".join(str(value) for value in values_by_test[code].values()),
                                "unidad": fields[0][2],
                                "observaciones": "Resultado sintético de demostración.",
                                "estatus": "aprobado",
                                "completada": True,
                                "is_revisada": True,
                                "estado_asignacion": "confirmada",
                                "fecha_confirmacion": date,
                            },
                        )
                        _, result_created = Resultado.objects.update_or_create(
                            prueba_muestra=assignment,
                            defaults={
                                "resultado": json.dumps(result_payload(fields, values_by_test[code])),
                                "fecha_medicion": date,
                                "usuario_medicion": operator,
                                "estatus": "aprobado",
                                "observaciones": "Resultado sintético de demostración.",
                            },
                        )
                        created["resultados"] += int(result_created)

                    sample.campos_adicionales = {
                        **(sample.campos_adicionales or {}),
                        "interpretacion": {
                            "conclusion": "Datos sintéticos para demostrar la evolución por punto de medición. El redactor debe reemplazarlos por resultados de laboratorio antes de cualquier decisión técnica.",
                            "comentarios_predefinidos": ["Demostración de tendencia histórica por punto de medición."],
                            "comentarios_manuales": [],
                            "graficas_activas": True,
                            "graficas_seleccionadas": list(TEST_CODES),
                            "updated_at": timezone.now().isoformat(),
                            "updated_by": operator.pk,
                        },
                    }
                    sample.is_ingresado = sample.is_resultado_ingresado = sample.is_revisado = True
                    sample.save(update_fields=["campos_adicionales", "is_ingresado", "is_resultado_ingresado", "is_revisado"])

                    report, report_created = Reporte.objects.get_or_create(
                        muestra=sample,
                        version=1,
                        defaults={
                            "consecutivo": f"R{DEMO_PREFIX}-{sample_id}",
                            "lote": lote,
                            "fecha_emision": date,
                            "fecha_generacion": date,
                            "usuario_emision": operator,
                            "estatus": "generado",
                            "conclusiones": "Informe sintético para demostración de tendencias.",
                            "snapshot": {"demo": True, "scope": "punto de medición", "sample": sample_id},
                        },
                    )
                    created["reportes"] += int(report_created)
                lote.recalcular_estado(save=True)
                if lote.estado != "reportado":
                    lote.estado = "reportado"
                    lote.save(update_fields=["estado", "fecha_actualizacion"])

        self.stdout.write(self.style.SUCCESS(
            "Demostración disponible en DEMO - DRAGA CUCHARA 05. "
            + ", ".join(f"{key}: {value}" for key, value in created.items())
        ))
