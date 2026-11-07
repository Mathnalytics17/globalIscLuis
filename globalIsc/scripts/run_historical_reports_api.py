#!/usr/bin/env python3
"""Generate resumable internal historic reports without exposing a password in argv."""
import getpass
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACTS = SCRIPT_DIR.parent / "outputs" / "migracion_historica_global_oil"


def main():
    password = getpass.getpass("Contraseña del administrador local: ")
    if not password:
        raise SystemExit("No se recibió contraseña.")
    environment = os.environ.copy()
    environment["DATAIA_IMPORT_PASSWORD"] = password
    command = [
        sys.executable, str(SCRIPT_DIR / "advance_historical_reports_via_api.py"),
        "--artifacts", str(ARTIFACTS), "--base-url", "http://localhost:8001",
        "--email", "admin@globaloil.local", "--password-env", "DATAIA_IMPORT_PASSWORD",
        "--apply", "--resume",
    ]
    raise SystemExit(subprocess.run(command, cwd=SCRIPT_DIR, env=environment).returncode)


if __name__ == "__main__":
    main()
