#!/usr/bin/env python3
"""Load approved technical catalogs through the local API, idempotently.

This is configuration ETL, not a Django ORM write.  It consumes only the
proposal produced by ``build_technical_configuration_proposal.py`` and never
uses sheets 06_Origenes_Metales, 07_Repertorio or 10_Notas_Tecnicas.

It deliberately creates no sample attributes for historic samples: an absent
technical criterion must remain absent until a source-backed mapping exists.
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path

from load_global_oil_via_api import Api


CATALOGS = {
    "NIVEL_CONTAMINACION": {
        "nombre": "Nivel de contaminación",
        "descripcion": "Código ISO 4406 por tipo de sistema. Los tres valores se evalúan por igualdad estricta.",
        "campos": [
            ("tipo_sistema_uso", "Tipo de sistema / uso", "texto", None, False),
            ("componentes_tipicos", "Componentes típicos", "texto", None, False),
            ("sensibilidad", "Sensibilidad", "texto", None, False),
            ("4um", "4 µm", "numero", "µm", True),
            ("6um", "6 µm", "numero", "µm", True),
            ("14um", "14 µm", "numero", "µm", True),
        ],
        "sample_field": ("nivel_contaminacion", "Nivel de contaminación objetivo", "Seleccione el código ISO 4406 aplicable al punto o muestra."),
    },
    "GRADO_VISCOSIDAD": {
        "nombre": "Grado de viscosidad",
        "descripcion": "Rangos de viscosidad e índice de viscosidad por grado, extraídos de la base técnica.",
        "campos": [
            ("familia", "Familia", "texto", None, False),
            ("vmin", "Viscosidad mínima", "decimal", "cSt", True),
            ("vmax", "Viscosidad máxima", "decimal", "cSt", True),
            ("iv_mono", "IV mono", "decimal", None, True),
            ("iv_multi", "IV multi", "decimal", None, True),
            ("notas", "Notas", "texto", None, False),
        ],
        "sample_field": ("grado_viscosidad", "Grado de viscosidad", "Grado declarado del lubricante o confirmado por el laboratorio."),
    },
    "TIPO_SISTEMA_USO": {
        "nombre": "Tipo de sistema / uso",
        "descripcion": "Criterio técnico para resolver límites de elementos por sistema.",
        "campos": [],
        "sample_field": ("tipo_sistema_uso", "Tipo de sistema / uso", "Sistema técnico aplicable para la evaluación de límites."),
    },
    "NIVEL_DESEMPENO": {
        "nombre": "Nivel de desempeño / especificación",
        "descripcion": "Matriz técnica de espuma y punto de chispa por especificación del lubricante.",
        "campos": [
            ("espuma_seq_i", "Espuma secuencia I", "texto", "mL/mL", True),
            ("espuma_seq_ii", "Espuma secuencia II", "texto", "mL/mL", True),
            ("espuma_seq_iii", "Espuma secuencia III", "texto", "mL/mL", True),
            ("punto_chispa_min", "Punto de chispa mínimo", "decimal", "°C", True),
        ],
        "sample_field": ("nivel_desempeno", "Nivel de desempeño / especificación", "Especificación técnica declarada o confirmada del lubricante."),
    },
}


def norm(value):
    return " ".join(str(value or "").split()).casefold()


def api_code(value):
    """Match Django SlugField without losing the human label (e.g. 23/21/17)."""
    text = unicodedata.normalize("NFKD", norm(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def records(api, path, params=None):
    value = api.get(path, params or {})
    if isinstance(value, list):
        return value
    # DRF list endpoints can be either bare arrays or paginated envelopes.
    # Treat the latter identically so idempotent reruns never re-create an
    # item-value pair that already exists.
    if isinstance(value, dict) and isinstance(value.get("results"), list):
        return value["results"]
    return [value]


def one_by_code(api, path, code, relation=None):
    matches = [row for row in records(api, path, {"search": code, **(relation or {})}) if norm(row.get("codigo")) == norm(code)]
    if len(matches) > 1:
        raise RuntimeError(f"Hay más de un registro para {path} código {code}: {[row['id'] for row in matches]}")
    return matches[0] if matches else None


def patch(api, path, payload):
    token = api.session.cookies.get("csrftoken")
    response = api._request("patch", path, json=payload, headers={"X-CSRFToken": token or "", "Referer": api.base_url})
    if not response.ok:
        raise RuntimeError(f"API PATCH {path} ({response.status_code}): {response.text}")
    return response.json()


def ensure(api, path, payload, *, code, relation=None):
    existing = one_by_code(api, path, code, relation)
    if not existing:
        return api.post(path, payload), "created"
    changed = {key: value for key, value in payload.items() if key not in {"catalogo", "version"} and existing.get(key) != value}
    if changed:
        existing = patch(api, f"{path}{existing['id']}/", changed)
        return existing, "updated"
    return existing, "unchanged"


def catalog_payload(code, spec, order):
    return {
        "nombre": spec["nombre"], "codigo": code.lower(), "tipo_muestra": "aceite",
        "descripcion": spec["descripcion"], "es_requerido_en_muestra": False,
        "permite_desconocido": True, "orden": order,
    }


def item_payload(catalog_id, version_id, item):
    return {
        "catalogo": catalog_id, "version": version_id, "nombre": item["nombre"],
        "codigo": api_code(item["codigo"]), "descripcion": None, "metadata": None,
    }


def item_values_payload(item, field_ids, item_id):
    values = []
    for code, value in (item.get("atributos") or {}).items():
        field_id = field_ids.get(code)
        if field_id and value not in (None, ""):
            values.append({"item": item_id, "campo": field_id, "valor": str(value)})
    return values


def write_inventory(path, proposal):
    lines = [
        "# Inventario de configuración técnica", "",
        "Fuente: Base_Conocimiento_Aceites_v9. Se excluyen explícitamente 06_Origenes_Metales, 07_Repertorio y 10_Notas_Tecnicas.", "",
        "| Tabla/proyecto | Contenido ETL | Uso |", "| --- | --- | --- |",
        "| CatalogoTecnico: Nivel de contaminación | códigos ISO y 4/6/14 µm | criterio de muestra; regla `eq` por componente |",
        "| CatalogoTecnico: Grado de viscosidad | familia, VMIN, VMAX, IV mono/multi | rango de viscosidad e IV condicionado por grado |",
        "| CatalogoTecnico: Tipo de sistema / uso | sistemas de la matriz de metales | criterio de límites de ELEMENTOS |",
        "| CatalogoTecnico: Nivel de desempeño / especificación | matriz de espuma y punto de chispa | criterio de las reglas condicionadas por especificación |",
        "| CampoTecnicoMuestra | cuatro selectores opcionales anteriores | vínculo explícito de una muestra con el catálogo, sin inferencias |",
        "| PruebaFuenteLimite / CriterioEvaluacionLimite | pendiente en el siguiente ETL | versiones publicables de reglas, no datos históricos |",
        "| COM_nombreprueba de REPORTES | pendiente de auditoría | contraste retrospectivo; nunca origen autónomo de un límite |", "",
        f"Catálogos previstos: {len(proposal['catalogos'])}; reglas ISO estrictas: {len(proposal['limites_catalogo']['iso4406_eq'])}; reglas de metales: {len(proposal['limites_catalogo']['metales_por_sistema'])}.", "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Carga por API los catálogos técnicos aprobados.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    proposal_path = args.artifacts / "homologacion" / "propuesta_configuracion_tecnica.json"
    if not proposal_path.is_file():
        parser.error("Falta la propuesta. Ejecute build_technical_configuration_proposal.py primero.")
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    unsupported = set(proposal["sources"]["included"]) - {"01_limites_metales.csv", "02_viscosidad.csv", "03_degradacion.csv", "05_iso4406.csv"}
    if unsupported or set(proposal["sources"]["excluded"]) != {"06_origenes_metales.csv", "07_repertorio.csv", "10_notas_tecnicas.csv"}:
        raise RuntimeError("La propuesta no mantiene el contrato de hojas aprobado.")
    inventory = args.artifacts / "homologacion" / "inventario_configuracion_tecnica.md"
    write_inventory(inventory, proposal)
    item_count = sum(len(c["items"]) for c in proposal["catalogos"])
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "writes": False, "catalogos": len(CATALOGS), "items": item_count, "campos_muestra": len(CATALOGS), "inventory": str(inventory)}, ensure_ascii=False))
        return
    if not args.email or not args.password:
        parser.error("--email y --password son obligatorios con --apply")
    proposal_by_code = {c["codigo"]: c for c in proposal["catalogos"]}
    api = Api(args.base_url, args.email, args.password)
    events = []
    for order, (code, spec) in enumerate(CATALOGS.items(), start=1):
        catalog, action = ensure(api, "technical-config/catalogs/", catalog_payload(code, spec, order), code=code.lower())
        events.append({"entity": "catalogo", "codigo": code, "id": catalog["id"], "action": action})
        version_id = catalog.get("version_actual")
        if not version_id:
            raise RuntimeError(f"El catálogo {code} no tiene versión actual.")
        field_ids = {}
        for field_order, (field_code, name, kind, unit, is_limit) in enumerate(spec["campos"], start=1):
            field, field_action = ensure(api, "technical-config/catalog-fields/", {
                "catalogo": catalog["id"], "nombre": name, "codigo": field_code, "tipo_dato": kind,
                "unidad": unit, "orden": field_order, "es_visible_en_muestra": False, "es_campo_limite": is_limit,
            }, code=field_code, relation={"catalogo": catalog["id"]})
            field_ids[field_code] = field["id"]
            events.append({"entity": "campo_catalogo", "catalogo": code, "codigo": field_code, "id": field["id"], "action": field_action})
        for item in proposal_by_code[code]["items"]:
            row, item_action = ensure(api, "technical-config/catalog-items/", item_payload(catalog["id"], version_id, item), code=api_code(item["codigo"]), relation={"catalogo": catalog["id"]})
            events.append({"entity": "item_catalogo", "catalogo": code, "codigo": item["codigo"], "id": row["id"], "action": item_action})
            for value in item_values_payload(item, field_ids, row["id"]):
                value_code = f"{row['id']}:{value['campo']}"
                existing_values = [candidate for candidate in records(api, "technical-config/catalog-item-values/", {"item": row["id"], "campo": value["campo"]}) if candidate.get("item") == row["id"] and candidate.get("campo") == value["campo"]]
                if len(existing_values) > 1:
                    raise RuntimeError(f"Hay valores duplicados para {value_code}.")
                if not existing_values:
                    api.post("technical-config/catalog-item-values/", value)
                    value_action = "created"
                elif str(existing_values[0].get("valor") or "") != value["valor"]:
                    patch(api, f"technical-config/catalog-item-values/{existing_values[0]['id']}/", {"valor": value["valor"]})
                    value_action = "updated"
                else:
                    value_action = "unchanged"
                events.append({"entity": "valor_item_catalogo", "catalogo": code, "codigo": value_code, "action": value_action})
        sample_code, sample_name, help_text = spec["sample_field"]
        sample, sample_action = ensure(api, "technical-config/sample-fields/", {
            "nombre_visible": sample_name, "codigo": sample_code, "tipo_muestra": "aceite", "catalogo": catalog["id"],
            "obligatorio": False, "permite_desconocido": True, "visible_en_ingreso": True,
            "visible_en_asignacion": True, "orden": order, "ayuda": help_text,
        }, code=sample_code, relation={"tipo_muestra": "aceite"})
        events.append({"entity": "campo_muestra", "codigo": sample_code, "id": sample["id"], "action": sample_action})
    report = args.artifacts / "reports" / "carga_catalogos_tecnicos_api.json"
    report.write_text(json.dumps({"mode": "apply", "sources": proposal["sources"], "events": events}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": "apply", "writes": True, "events": len(events), "report": str(report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
