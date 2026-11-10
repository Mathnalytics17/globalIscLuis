#!/usr/bin/env python3
"""Launch the four resumable physical-result API import shards from one password prompt."""
import getpass
import os
import subprocess
import sys
import argparse
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACTS = SCRIPT_DIR.parent / "outputs" / "migracion_historica_global_oil"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--password-env",
        default="DATAIA_IMPORT_PASSWORD",
        help="Nombre de la variable de entorno que contiene la contraseña.",
    )
    args = parser.parse_args()

    password = os.environ.get(args.password_env) or getpass.getpass("Contraseña del administrador local: ")
    if not password:
        raise SystemExit("No se recibió contraseña.")
    environment = os.environ.copy()
    environment[args.password_env] = password
    logs = ARTIFACTS / "reports" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    children = []
    for shard in range(4):
        command = [
            sys.executable, str(SCRIPT_DIR / "submit_compound_results_via_api.py"),
            "--artifacts", str(ARTIFACTS),
            "--sample-test-map", str(ARTIFACTS / "staging" / "oa_pruebas_muestra.json"),
            "--payload-file", "api_result_payloads_physical.jsonl",
            "--report-file", f"carga_api_resultados_fisicos_forms_shard{shard}.json",
            "--base-url", "http://localhost:8001",
            "--email", "admin@globaloil.local",
            "--password-env", args.password_env,
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
