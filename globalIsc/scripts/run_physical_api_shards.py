#!/usr/bin/env python3
"""Launch resumable physical-result API import shards from one password prompt."""
import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ARTIFACTS = SCRIPT_DIR.parent / "outputs" / "migracion_historica_global_oil"


def main():
    parser = argparse.ArgumentParser(description="Carga resultados físicos por API en cuatro particiones reanudables.")
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--email", default="admin@globaloil.local")
    args = parser.parse_args()
    artifacts = args.artifacts.resolve()
    if not artifacts.is_dir():
        parser.error(f"No existe la carpeta de artefactos: {artifacts}")
    password = getpass.getpass("Contraseña del administrador local: ")
    if not password:
        raise SystemExit("No se recibió contraseña.")
    environment = os.environ.copy()
    environment["DATAIA_IMPORT_PASSWORD"] = password
    logs = artifacts / "reports" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    children = []
    for shard in range(4):
        command = [
            sys.executable, str(SCRIPT_DIR / "submit_compound_results_via_api.py"),
            "--artifacts", str(artifacts),
            "--sample-test-map", str(artifacts / "staging" / "oa_pruebas_muestra.json"),
            "--payload-file", "api_result_payloads_physical.jsonl",
            "--report-file", f"carga_api_resultados_fisicos_forms_shard{shard}.json",
            "--base-url", args.base_url,
            "--email", args.email,
            "--password-env", "DATAIA_IMPORT_PASSWORD",
            "--apply", "--resume",
            "--batch-shard-count", "4", "--batch-shard-index", str(shard),
        ]
        stdout = (logs / f"physical_shard{shard}.out.log").open("w", encoding="utf-8")
        stderr = (logs / f"physical_shard{shard}.err.log").open("w", encoding="utf-8")
        children.append((shard, subprocess.Popen(command, cwd=SCRIPT_DIR, env=environment, stdout=stdout, stderr=stderr), stdout, stderr))
    for shard, child, stdout, stderr in children:
        status = child.wait()
        stdout.close(); stderr.close()
        print(f"shard={shard} exit={status}", flush=True)
    if any(child.returncode for _, child, _, _ in children):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
