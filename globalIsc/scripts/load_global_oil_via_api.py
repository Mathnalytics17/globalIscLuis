#!/usr/bin/env python3
"""HTTP-only loader skeleton for the local API; direct ORM writes are forbidden here."""
import argparse
import csv
import json
import time
from pathlib import Path
import requests


class Api:
    def __init__(self, base_url, email, password):
        self.session = requests.Session(); self.base_url = base_url.rstrip("/")
        csrf = self._request("get", "/users/csrf/")
        csrf.raise_for_status()
        token = self.session.cookies.get("csrftoken")
        response = self._request("post", "/users/login/", json={"email": email, "password": password}, headers={"X-CSRFToken": token or "", "Referer": self.base_url})
        response.raise_for_status()
    def _request(self, method, path, **kwargs):
        """Retry transient local API/Redis failures without duplicating writes."""
        url = f"{self.base_url}/api/{path.lstrip('/')}"
        last_error = None
        for attempt in range(5):
            try:
                response = self.session.request(method, url, timeout=90, **kwargs)
                if response.status_code < 500:
                    return response
                last_error = RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
            except requests.RequestException as error:
                last_error = error
            time.sleep(1 + attempt * 2)
        raise RuntimeError(f"API {method.upper()} {path} no respondió tras reintentos: {last_error}")
    def post(self, path, payload):
        token = self.session.cookies.get("csrftoken")
        response = self._request("post", path, json=payload, headers={"X-CSRFToken": token or "", "Referer": self.base_url})
        if not response.ok:
            raise RuntimeError(f"API POST {path} ({response.status_code}): {response.text}")
        return response.json()
    def post_file(self, path, file_name, content, field_name="file"):
        token = self.session.cookies.get("csrftoken")
        response = self._request(
            "post", path,
            files={field_name: (file_name, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers={"X-CSRFToken": token or "", "Referer": self.base_url},
        )
        if not response.ok:
            raise RuntimeError(f"API POST {path} ({response.status_code}): {response.text}")
        return response.json()
    def get(self, path, params=None):
        response = self._request("get", path, params=params or {})
        response.raise_for_status(); data = response.json()
        return data.get("results", data) if isinstance(data, dict) else data


def raw_rows(path):
    return [json.loads(line)["data"] for line in path.open(encoding="utf-8") if line.strip()]


def norm(value):
    return " ".join(str(value or "").split())


def main():
    parser = argparse.ArgumentParser(description="Carga activos por API local; use --apply para escribir.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email"); parser.add_argument("--password")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    points_file = args.artifacts / "homologacion" / "puntos_medicion.csv"
    if not points_file.is_file(): parser.error("Ejecute primero etl_global_oil_domain.py")
    points = list(csv.DictReader(points_file.open(encoding="utf-8-sig")))
    companies = sorted({norm(point["empresa_origen"]) for point in points}, key=str.casefold)
    machines = sorted({(norm(point["empresa_origen"]), norm(point["maquina_origen"])) for point in points}, key=lambda item: (item[0].casefold(), item[1].casefold()))
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "api": args.base_url, "companies_to_create": len(companies), "machines_to_create": len(machines), "points_to_create": len(points), "writes": False})); return
    if not args.email or not args.password:
        parser.error("--email y --password son obligatorios con --apply")
    api = Api(args.base_url, args.email, args.password)
    company_ids, machine_ids, events = {}, {}, []
    # POST de máquina activa ensure_machine_tree_node: el nodo queda bajo la raíz
    # de empresa sin tocar Carpeta directamente desde esta ETL.
    for name in companies:
        matches = [item for item in api.get("companies/buscar/", {"nombre": name}) if norm(item.get("nombre")) == name]
        created = matches[0] if matches else api.post("companies/", {"nombre": name, "is_active": True})
        company_ids[name] = created["id"]; events.append({"entity": "empresa", "source": name, "id": created["id"]})
    for company, machine in machines:
        matches = [item for item in api.get("machines/", {"empresa": company_ids[company], "search": machine}) if norm(item.get("nombre")) == machine]
        created = matches[0] if matches else api.post("machines/", {"empresa": company_ids[company], "nombre": machine, "codigo_equipo": machine, "activo": True})
        machine_ids[(company, machine)] = created["id"]; events.append({"entity": "maquina", "source": f"{company} / {machine}", "id": created["id"]})
    for point in points:
        machine_id = machine_ids[(norm(point["empresa_origen"]), norm(point["maquina_origen"]))]
        # The approved ETL identity is machine + source PLACA.  Names are
        # aliases, so they must not create duplicate points when code matches.
        matches = [item for item in api.get("sampling-points/", {"machine": machine_id}) if (
            norm(item.get("codigo")) == norm(point["codigo_punto"])
        )] if point["estado"] == "LISTO_PLACA" else [item for item in api.get("sampling-points/", {"machine": machine_id}) if (
            norm(item.get("nombre")) == norm(point["nombre_punto"])
            and norm(item.get("codigo")) == norm(point["codigo_punto"])
        )]
        created = matches[0] if matches else api.post("sampling-points/", {"maquina": machine_id, "nombre": point["nombre_punto"], "codigo": point["codigo_punto"], "lubricante": ""})
        events.append({"entity": "punto_muestreo", "source": f'{point["nombre_punto"]} · {point["codigo_punto"]}', "id": created["id"]})
    (args.artifacts / "reports" / "carga_api_activos.json").write_text(json.dumps({"mode": "api", "events": events}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": "apply", "writes": True, "created": len(events)}))


if __name__ == "__main__": main()
