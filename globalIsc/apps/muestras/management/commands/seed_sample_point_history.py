"""Crea un historial sintético, visible e idempotente para una muestra existente."""

import copy
import json
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.activesTree.api.models.index import AsignacionPuntoMuestreo
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.resultado.api.models.index import Resultado


DEMO_NOTE = "Dato sintético de demostración para tendencias. No usar para decisiones operacionales."


def _numeric(value):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _format(value, original):
    if isinstance(original, str) and "." not in original and "," not in original:
        return str(int(round(value)))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _vary_payload(raw_payload, period, periods):
    """Keep the real result structure while generating a gradual plausible history."""
    try:
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else copy.deepcopy(raw_payload)
    except (TypeError, ValueError):
        return raw_payload
    if not isinstance(payload, dict):
        return raw_payload

    # Earlier samples are slightly lower, with a tiny deterministic variation.
    factor = 0.68 + ((period + 1) / (periods + 1)) * 0.26
    for index, value_item in enumerate(payload.get("values") or []):
        value = _numeric(value_item.get("value"))
        if value is None:
            continue
        variation = ((index % 3) - 1) * 0.015 * max(abs(value), 1)
        generated = max(0, value * factor + variation)
        formatted = _format(generated, value_item.get("value"))
        value_item["value"] = formatted
        value_item["value_label"] = formatted
        value_item["observacion"] = "Resultado sintético de demostración"
    payload["saved_at"] = timezone.now().isoformat()
    return json.dumps(payload)


class Command(BaseCommand):
    help = "Crea muestras históricas sintéticas para el mismo equipo y punto de una muestra."

    def add_arguments(self, parser):
        parser.add_argument("--sample", required=True, help="ID de la muestra de referencia.")
        parser.add_argument("--periods", type=int, default=6, help="Históricos previos a crear (2 a 12).")

    def handle(self, *args, **options):
        periods = max(2, min(options["periods"], 12))
        source = (
            Muestra.objects.select_related("lote", "lote__cliente_empresa", "referencia_equipo", "usuario_registro")
            .filter(pk=options["sample"])
            .first()
        )
        if not source:
            raise CommandError("No existe la muestra indicada.")
        if not source.lote_id or not source.lote.cliente_empresa_id or not source.referencia_equipo_id:
            raise CommandError("La muestra debe tener lote, empresa y equipo registrados.")
        point_assignment = (
            AsignacionPuntoMuestreo.objects.filter(muestra=source, activa=True)
            .select_related("punto_muestreo")
            .first()
        )
        if not point_assignment:
            raise CommandError("La muestra debe tener un punto de medición activo.")
        source_tests = list(
            PruebaMuestra.objects.filter(muestra=source)
            .select_related("prueba", "usuario_solicitud", "usuario_medicion", "usuario_revision")
            .prefetch_related("resultados")
        )
        if not source_tests:
            raise CommandError("La muestra no tiene pruebas para usar como estructura del histórico.")

        created = {"lotes": 0, "muestras": 0, "resultados": 0}
        source_date = source.fecha_toma or timezone.now()
        with transaction.atomic():
            for period in range(periods):
                # Suficientemente separado para que el eje temporal sea legible,
                # y siempre anterior a la muestra real que se está interpretando.
                date = source_date - timedelta(days=28 * (periods - period))
                lot_id = f"DEMO-H-{source.id[-4:]}-{period + 1:02d}"
                lot, lot_created = LoteMuestras.objects.get_or_create(
                    pk=lot_id,
                    defaults={
                        "tipo_cliente": "registrado",
                        "cliente_empresa": source.lote.cliente_empresa,
                        "contacto_nombre": "Demostración técnica",
                        "contacto_email": "demo-historico@globaloil.local",
                        "fecha_envio": date.date(),
                        "fecha_recepcion": date.date(),
                        "tipo_gestion": source.lote.tipo_gestion,
                        "estado": "reportado",
                        "observaciones": f"{DEMO_NOTE} Fuente: {source.id}.",
                        "usuario_registro": source.usuario_registro,
                    },
                )
                created["lotes"] += int(lot_created)
                sample = Muestra.objects.filter(lote=lot).first()
                if not sample:
                    sample = Muestra.objects.create(
                        lote=lot,
                        fecha_toma=date,
                        contacto_cliente=source.contacto_cliente,
                        referencia_equipo=source.referencia_equipo,
                        equipo_placa=source.equipo_placa,
                        periodo_servicio_aceite=max(0, (source.periodo_servicio_aceite or 0) + (period - periods) * 120),
                        unidad_periodo_aceite=source.unidad_periodo_aceite or "horas",
                        periodo_servicio_equipo=max(0, (source.periodo_servicio_equipo or 0) + (period - periods) * 180),
                        unidad_periodo_equipo=source.unidad_periodo_equipo or "horas",
                        tipo_muestra=source.tipo_muestra,
                        condicion=source.condicion,
                        referencia_marca=source.referencia_marca,
                        observaciones=f"{DEMO_NOTE} Fuente: {source.id}.",
                        usuario_registro=source.usuario_registro,
                        is_ingresado=True,
                        is_resultado_ingresado=True,
                        is_revisado=True,
                    )
                    created["muestras"] += 1
                AsignacionPuntoMuestreo.objects.get_or_create(
                    muestra=sample,
                    activa=True,
                    defaults={
                        "punto_muestreo": point_assignment.punto_muestreo,
                        "origen": "manual",
                        "asignado_por": source.usuario_registro,
                    },
                )

                for source_test in source_tests:
                    defaults = {
                        "usuario_solicitud": source_test.usuario_solicitud or source.usuario_registro,
                        "usuario_medicion": source_test.usuario_medicion or source.usuario_registro,
                        "usuario_revision": source_test.usuario_revision or source.usuario_registro,
                        "fecha_medicion": date,
                        "fecha_revision": date,
                        "equipo_configurado": source_test.equipo_configurado,
                        "metodo_configurado": source_test.metodo_configurado,
                        "condicion_catalogo": source_test.condicion_catalogo,
                        "condicion_configurada": source_test.condicion_configurada,
                        "unidad_configurada": source_test.unidad_configurada,
                        "configuracion_resultados": copy.deepcopy(source_test.configuracion_resultados),
                        "lote_predefinido": source_test.lote_predefinido,
                        "criterio_evaluacion": source_test.criterio_evaluacion,
                        "fuente_limite": source_test.fuente_limite,
                        "criterio_limite_catalogo": source_test.criterio_limite_catalogo,
                        "criterio_limite_item": source_test.criterio_limite_item,
                        "criterio_limite_escala": source_test.criterio_limite_escala,
                        "criterio_limite_escala_item": source_test.criterio_limite_escala_item,
                        "criterio_limite_valor": source_test.criterio_limite_valor,
                        "estado_asignacion": "confirmada",
                        "fecha_confirmacion": date,
                        "valor": source_test.valor,
                        "unidad": source_test.unidad,
                        "observaciones": "Resultado sintético de demostración.",
                        "estatus": "aprobado",
                        "completada": True,
                        "is_revisada": True,
                    }
                    test, _ = PruebaMuestra.objects.get_or_create(
                        muestra=sample, prueba=source_test.prueba, defaults=defaults,
                    )
                    source_result = next(iter(source_test.resultados.all()), None)
                    if source_result:
                        _, result_created = Resultado.objects.update_or_create(
                            prueba_muestra=test,
                            defaults={
                                "resultado": _vary_payload(source_result.resultado, period, periods),
                                "fecha_medicion": date,
                                "usuario_medicion": source_test.usuario_medicion or source.usuario_registro,
                                "estatus": "aprobado",
                                "observaciones": "Resultado sintético de demostración.",
                            },
                        )
                        created["resultados"] += int(result_created)
                sample.is_ingresado = sample.is_resultado_ingresado = sample.is_revisado = True
                sample.save(update_fields=["is_ingresado", "is_resultado_ingresado", "is_revisado"])
                lot.estado = "reportado"
                lot.save(update_fields=["estado", "fecha_actualizacion"])

        self.stdout.write(self.style.SUCCESS(
            f"Histórico demo creado para {source.referencia_equipo.nombre} / "
            f"{point_assignment.punto_muestreo.nombre}. "
            + ", ".join(f"{key}: {value}" for key, value in created.items())
        ))
