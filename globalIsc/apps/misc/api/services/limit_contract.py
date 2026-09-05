from copy import deepcopy

from django.utils.text import slugify

from apps.misc.api.models.dynamicTechnicalConfig.index import (
    PruebaFuenteLimite,
    PruebaLimiteCampo,
)


def comparison_from_component(component):
    value = getattr(component, "tipo_dato", "numerico") if component else "numerico"
    return {
        "numerico": "numerica",
        "booleano": "booleano",
        "escala": "escala",
        "escala_ordinal": "escala",
        "comentario": "comentario",
        "opcion": "escala",
        "texto": "comentario",
    }.get(value, "numerica")


def test_limit_leaves(prueba):
    """Describe la estructura evaluable mediante códigos estables, no IDs efímeros."""
    leaves = []
    resultados = prueba.resultados.filter(activo=True).order_by("orden", "id")

    for resultado in resultados:
        divisiones = resultado.divisiones.filter(activo=True).order_by("orden", "id")
        if not divisiones.exists():
            leaves.append(_leaf(resultado.nombre, resultado=resultado))
            continue

        for division in divisiones:
            componentes = division.componentes.filter(activo=True).order_by("orden", "id")
            if componentes.exists():
                for componente in componentes:
                    leaves.append(_leaf(
                        " ".join(filter(None, [resultado.nombre, division.nombre, componente.nombre])).strip(),
                        resultado=resultado,
                        division=division,
                        componente=componente,
                    ))
            else:
                leaves.append(_leaf(
                    " ".join(filter(None, [resultado.nombre, division.nombre])).strip(),
                    resultado=resultado,
                    division=division,
                ))

    if not leaves:
        leaves.append(_leaf(prueba.nombre_variable or prueba.acronimo or f"Prueba {prueba.pk}"))
    return leaves


def reconcile_limit_contract(prueba):
    """
    Conserva las reglas por código y las reconecta con la estructura actual.

    Editar una prueba recrea sus nodos anidados. Esta reconciliación evita que los
    límites, operadores y bandas queden asociados a IDs eliminados.
    """
    leaves = test_limit_leaves(prueba)
    sources = PruebaFuenteLimite.objects.filter(prueba=prueba)
    reconciled = 0

    for source in sources:
        decision = deepcopy(source.configuracion_regla or {})
        configured = decision.get("campos") if isinstance(decision.get("campos"), list) else []
        configured_by_code = {
            str(item.get("codigo")): item
            for item in configured
            if isinstance(item, dict) and item.get("codigo")
        }
        fields_by_code = {
            str(field.codigo): field
            for field in PruebaLimiteCampo.objects.filter(fuente_limite=source)
        }
        canonical_fields = []

        for order, leaf in enumerate(leaves, start=1):
            saved = deepcopy(configured_by_code.get(leaf["codigo"]) or {})
            stored = fields_by_code.get(leaf["codigo"])
            component = leaf.get("componente")
            comparison = (
                saved.get("tipo_comparacion")
                or (stored.tipo_comparacion if stored else None)
                or comparison_from_component(component)
            )
            informative = (
                comparison == "comentario"
                or saved.get("informativo") is True
                or saved.get("evalua") is False
            )
            origin = (
                saved.get("origen_limite")
                or ("informativo" if informative else ("catalogo" if source.tipo_limite == "catalogo" else "directo"))
            )
            result = leaf.get("resultado")
            unit = getattr(result, "unidad_medida", "") or saved.get("unidad") or (stored.unidad if stored else "") or ""
            operator = saved.get("operador") or (stored.operador if stored else None) or (
                "eq" if comparison == "booleano" else "max"
            )

            canonical = {
                **saved,
                "codigo": leaf["codigo"],
                "nombre": getattr(component, "nombre", None) or leaf["nombre"],
                "resultado": getattr(result, "pk", None),
                "resultadoNombre": getattr(result, "nombre", "") or "",
                "division": getattr(leaf.get("division"), "pk", None),
                "divisionNombre": getattr(leaf.get("division"), "nombre", "") or "",
                "componente": getattr(component, "pk", None),
                "tipo": getattr(component, "tipo_dato", None) or saved.get("tipo") or "numerico",
                "tipo_comparacion": comparison,
                "unidad": unit,
                "escala": getattr(component, "escala_comparacion_id", None) or "",
                "escala_comparacion": getattr(component, "escala_comparacion_id", None) or "",
                "etiqueta_verdadero": getattr(component, "etiqueta_verdadero", None) or saved.get("etiqueta_verdadero") or "Sí",
                "etiqueta_falso": getattr(component, "etiqueta_falso", None) or saved.get("etiqueta_falso") or "No",
                "trueLabel": getattr(component, "etiqueta_verdadero", None) or saved.get("trueLabel") or "Sí",
                "falseLabel": getattr(component, "etiqueta_falso", None) or saved.get("falseLabel") or "No",
                "operador": operator,
                "origen_limite": origin,
                "participa": not informative if saved.get("participa") is None else saved.get("participa"),
                "evalua": not informative if saved.get("evalua") is None else saved.get("evalua"),
                "informativo": informative,
                "valor_global": saved.get(
                    "valor_global",
                    stored.valor_global if stored and stored.valor_global not in [None, ""] else {},
                ),
                "evaluacion_booleano": saved.get(
                    "evaluacion_booleano",
                    stored.evaluacion_opciones if stored else None,
                ),
            }
            canonical_fields.append(canonical)

            if informative or canonical["participa"] is False or canonical["evalua"] is False:
                if stored:
                    stored.activo = False
                    stored.save(update_fields=["activo", "updated_at"])
                continue

            defaults = {
                "nombre": leaf["nombre"],
                "operador": operator,
                "tipo_comparacion": comparison,
                "escala_comparacion_id": getattr(component, "escala_comparacion_id", None),
                "evaluacion_opciones": saved.get("evaluacion_booleano") or (
                    stored.evaluacion_opciones if stored else None
                ),
                "valor_global": (
                    stored.valor_global if stored and stored.valor_global not in [None, ""] else None
                ),
                "unidad": unit,
                "resultado": result,
                "division": leaf.get("division"),
                "componente": component,
                "orden": order,
                "activo": True,
                "deleted_at": None,
            }
            PruebaLimiteCampo.objects.update_or_create(
                fuente_limite=source,
                codigo=leaf["codigo"],
                defaults=defaults,
            )

        current_codes = {leaf["codigo"] for leaf in leaves}
        PruebaLimiteCampo.objects.filter(fuente_limite=source).exclude(
            codigo__in=current_codes
        ).update(activo=False)
        decision["campos"] = canonical_fields
        decision["informativos"] = [
            field["codigo"] for field in canonical_fields if field.get("informativo")
        ]
        source.configuracion_regla = decision
        source.save(update_fields=["configuracion_regla", "updated_at"])
        reconciled += 1

    return reconciled


def _leaf(nombre, resultado=None, division=None, componente=None):
    return {
        "nombre": nombre or "Campo",
        "codigo": slugify(nombre or "campo").replace("-", "_"),
        "resultado": resultado,
        "division": division,
        "componente": componente,
    }
