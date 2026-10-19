"""Crea una bandeja operativa vistosa, segura e idempotente para demostraciones.

Esta semilla no borra datos. Sus identificadores ``SHOW-*`` dejan claro que son
registros de demostración y permiten ejecutarla varias veces sin duplicarlos.
"""

import json
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.activesTree.api.models.index import AsignacionPuntoMuestreo, PuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.models.tipoGestionMuestra.index import TipoGestionMuestra
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.reporte.api.models.index import Reporte
from apps.resultado.api.models.index import Resultado
from apps.users.api.models.index import User


TEST_CODES = ("INDVISC", "OXID", "NTR", "ESPDES", "AGUA")


def _payload(code, offset=0):
    fields_by_test = {
        "INDVISC": [("visc_40", "Viscosidad cinemática 40 °C", "cSt")],
        "OXID": [("oxid", "Oxidación", "Abs/0.1 mm")],
        "NTR": [("nitr", "Nitración", "Abs/0.1 mm")],
        "ESPDES": [("fe", "Hierro", "ppm"), ("cu", "Cobre", "ppm"), ("si", "Silicio", "ppm")],
        "AGUA": [("agua", "Contenido de agua", "%")],
    }
    values_by_test = {
        "INDVISC": {"visc_40": round(220 + offset * 1.7, 2)},
        "OXID": {"oxid": round(0.045 + offset * 0.006, 3)},
        "NTR": {"nitr": round(0.012 + offset * 0.003, 3)},
        "ESPDES": {"fe": 18 + offset * 6, "cu": 3 + offset, "si": 8 + offset * 2},
        "AGUA": {"agua": round(0.025 + offset * 0.007, 3)},
    }
    fields = fields_by_test[code]
    values = values_by_test[code]
    return (
        fields,
        values,
        json.dumps({
            "fields": [{"key": key, "label": label, "componente_nombre": label, "unidad": unit} for key, label, unit in fields],
            "values": [{"key": key, "value": str(value), "value_label": str(value), "observacion": "Dato sintético de demostración."} for key, value in values.items()],
        }),
    )


class Command(BaseCommand):
    help = "Crea lotes, muestras, resultados e informes sintéticos para recorrer el flujo de la aplicación."

    def _sample(self, *, lot, identifier, machine, point, operator, date, entered, results, reviewed, note):
        sample, created = Muestra.objects.get_or_create(
            id=identifier,
            defaults={
                "lote": lot,
                "fecha_toma": date,
                "referencia_equipo": machine,
                "equipo_placa": machine.codigo_equipo,
                "periodo_servicio_aceite": 740 + len(identifier) * 5,
                "unidad_periodo_aceite": "horas",
                "periodo_servicio_equipo": 8600 + len(identifier) * 75,
                "unidad_periodo_equipo": "horas",
                "tipo_muestra": "aceite",
                "condicion": "usada",
                "observaciones": note,
                "usuario_registro": operator,
                "is_ingresado": entered,
                "is_resultado_ingresado": results,
                "is_revisado": reviewed,
            },
        )
        AsignacionPuntoMuestreo.objects.get_or_create(
            muestra=sample,
            activa=True,
            defaults={"punto_muestreo": point, "origen": "lote", "asignado_por": operator},
        )
        return sample, created

    def _tests(self, *, sample, tests, operator, date, result_count, reviewed, offset):
        created_results = 0
        for position, code in enumerate(TEST_CODES):
            assignment, _ = PruebaMuestra.objects.get_or_create(
                muestra=sample,
                prueba=tests[code],
                defaults={
                    "usuario_solicitud": operator,
                    "estado_asignacion": "confirmada",
                    "fecha_confirmacion": date,
                    "estatus": "aprobado" if reviewed else ("completado" if position < result_count else "pendiente"),
                    "completada": position < result_count,
                    "is_revisada": reviewed and position < result_count,
                    "usuario_medicion": operator if position < result_count else None,
                    "usuario_revision": operator if reviewed and position < result_count else None,
                    "fecha_medicion": date if position < result_count else None,
                    "fecha_revision": date if reviewed and position < result_count else None,
                    "observaciones": "Resultado de demostración para recorrido comercial.",
                },
            )
            if position >= result_count:
                continue
            fields, values, payload = _payload(code, offset + position)
            _, result_created = Resultado.objects.update_or_create(
                prueba_muestra=assignment,
                defaults={
                    "resultado": payload,
                    "fecha_medicion": date,
                    "usuario_medicion": operator,
                    "estatus": "aprobado" if reviewed else "preliminar",
                    "observaciones": "Resultado sintético de demostración.",
                },
            )
            created_results += int(result_created)
        return created_results

    @transaction.atomic
    def handle(self, *args, **options):
        operator = User.objects.filter(role=User.Role.GLOBAL, is_active=True).first() or User.objects.filter(is_active=True).first()
        management_type = TipoGestionMuestra.objects.filter(activo=True).order_by("id").first()
        tests = {item.acronimo: item for item in Prueba.objects.filter(acronimo__in=TEST_CODES, activo=True)}
        company = Empresa.objects.filter(nombre="Empresa Minera Demo").first()
        if not operator or not management_type or not company or len(tests) != len(TEST_CODES):
            raise CommandError("Ejecute seed_demo_environment primero: faltan usuario, empresa, tipo de gestión o pruebas demo.")

        machines = list(Maquina.objects.filter(empresa=company, activo=True).order_by("codigo_equipo")[:4])
        points = list(PuntoMuestreo.objects.filter(maquina__in=machines, activo=True).select_related("maquina").order_by("maquina__codigo_equipo", "id"))
        if len(points) < 4:
            raise CommandError("La empresa demo necesita al menos cuatro puntos de medida activos.")

        now = timezone.now()
        scenarios = (
            ("SHOW-REC-01", "recibido", now - timedelta(days=1), 2, 0, False, False, "Recepción pendiente de ingreso al laboratorio."),
            ("SHOW-LAB-01", "en_laboratorio", now - timedelta(days=5), 3, 0, True, False, "Ensayos confirmados y pendientes de resultados."),
            ("SHOW-PAR-01", "parcial", now - timedelta(days=4), 4, 2, True, False, "Lote con resultados parcialmente cargados."),
            ("SHOW-CMP-01", "resultados_completos", now - timedelta(days=2), 3, 5, True, False, "Resultados completos pendientes de revisión."),
            ("SHOW-RPT-01", "reportado", now - timedelta(days=21), 3, 5, True, True, "Informes listos para consultar y presentar al cliente."),
        )

        totals = {"lotes": 0, "muestras": 0, "resultados": 0, "reportes": 0}
        for lot_index, (lot_id, expected_status, date, sample_count, result_count, entered, reviewed, note) in enumerate(scenarios):
            lot, lot_created = LoteMuestras.objects.get_or_create(
                id=lot_id,
                defaults={
                    "tipo_cliente": "registrado",
                    "cliente_empresa": company,
                    "contacto_nombre": "Equipo de confiabilidad - demostración",
                    "contacto_email": "demo@globaloil.local",
                    "fecha_envio": date.date(),
                    "fecha_recepcion": date.date() if entered else None,
                    "tipo_gestion": management_type,
                    "estado": expected_status,
                    "observaciones": f"{note} Datos sintéticos; no usar para decisiones reales.",
                    "usuario_registro": operator,
                },
            )
            totals["lotes"] += int(lot_created)
            created_samples = []
            for sample_index in range(sample_count):
                point = points[(lot_index + sample_index) % len(points)]
                sample, sample_created = self._sample(
                    lot=lot,
                    identifier=f"SM{lot_index + 1}{sample_index + 1:02d}26",
                    machine=point.maquina,
                    point=point,
                    operator=operator,
                    date=date + timedelta(hours=sample_index),
                    entered=entered,
                    results=bool(result_count and (expected_status != "parcial" or sample_index < 2)),
                    reviewed=reviewed,
                    note=note,
                )
                totals["muestras"] += int(sample_created)
                per_sample_results = result_count if expected_status != "parcial" or sample_index < 2 else 0
                totals["resultados"] += self._tests(
                    sample=sample,
                    tests=tests,
                    operator=operator,
                    date=date,
                    result_count=per_sample_results if entered else 0,
                    reviewed=reviewed,
                    offset=lot_index + sample_index,
                )
                created_samples.append(sample)

            if expected_status == "reportado":
                report_states = ("aprobado", "enviado", "pendiente_aprobacion")
                for sample_index, sample in enumerate(created_samples):
                    report_status = report_states[sample_index % len(report_states)]
                    report, report_created = Reporte.objects.get_or_create(
                        muestra=sample,
                        version=1,
                        defaults={
                            "consecutivo": f"R-{lot_id}-{sample.id}",
                            "lote": lot,
                            "fecha_emision": date + timedelta(days=1),
                            "fecha_generacion": date + timedelta(days=1),
                            "fecha_aprobacion": date + timedelta(days=2) if report_status in {"aprobado", "enviado"} else None,
                            "fecha_envio": date + timedelta(days=3) if report_status == "enviado" else None,
                            "usuario_emision": operator,
                            "usuario_aprobacion": operator if report_status in {"aprobado", "enviado"} else None,
                            "usuario_envio": operator if report_status == "enviado" else None,
                            "estatus": report_status,
                            "visible_cliente": report_status in {"aprobado", "enviado"},
                            "conclusiones": "Informe sintético para presentar el flujo completo de Global Oil.",
                            "notas_internas": "Registro demostrativo.",
                            "snapshot": {"demo": True, "scenario": "showcase", "sample": sample.id},
                        },
                    )
                    totals["reportes"] += int(report_created)

            lot.recalcular_estado(save=True)
            if lot.estado != expected_status:
                lot.estado = expected_status
                lot.save(update_fields=["estado", "fecha_actualizacion"])

        self.stdout.write(self.style.SUCCESS(
            "Bandeja demostrativa lista: " + ", ".join(f"{key}: {value}" for key, value in totals.items())
        ))
