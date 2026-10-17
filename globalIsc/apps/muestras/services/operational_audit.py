"""Servicios de auditoría operacional, sin lógica de presentación."""

from apps.muestras.api.models.auditoria import EventoAuditoriaOperativa


def record_operational_event(
    *,
    actor=None,
    action,
    entity_type,
    entity_id,
    entity_label="",
    empresa=None,
    lote=None,
    muestra=None,
    prueba_muestra=None,
    reporte=None,
    maquina=None,
    punto_muestreo=None,
    detail="",
    reason="",
    before=None,
    after=None,
    metadata=None,
    origin="ui",
    correlation_id="",
):
    """Persist an append-only event in the same business transaction.

    Callers explicitly pass context rather than relying on generic model signals;
    this keeps bulk imports and automatic state changes distinguishable.
    """
    if muestra is not None:
        lote = lote or muestra.lote
        maquina = maquina or muestra.referencia_equipo
        if punto_muestreo is None:
            assignment = muestra.asignaciones_punto_muestreo.filter(activa=True).select_related("punto_muestreo").first()
            punto_muestreo = assignment.punto_muestreo if assignment else None
    if lote is not None:
        empresa = empresa or lote.cliente_empresa
    if maquina is not None:
        empresa = empresa or maquina.empresa

    return EventoAuditoriaOperativa.objects.create(
        actor=actor,
        empresa=empresa,
        lote=lote,
        muestra=muestra,
        prueba_muestra=prueba_muestra,
        reporte=reporte,
        maquina=maquina,
        punto_muestreo=punto_muestreo,
        tipo_entidad=entity_type,
        entidad_id=str(entity_id),
        entidad_etiqueta=entity_label or str(entity_id),
        accion=action,
        detalle=detail or "",
        motivo=reason or "",
        estado_anterior=before or {},
        estado_nuevo=after or {},
        metadata=metadata or {},
        origen=origin,
        correlation_id=correlation_id or "",
    )
