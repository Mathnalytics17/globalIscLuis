#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"

if [[ -z "${DEMO_DEFAULT_PASSWORD:-}" || ${#DEMO_DEFAULT_PASSWORD} -lt 12 ]]; then
  echo "Defina DEMO_DEFAULT_PASSWORD con al menos 12 caracteres antes de ejecutar el bootstrap." >&2
  exit 1
fi

# Reinicio completo y repetible para un entorno demo. No use este script sobre
# datos que deban conservarse: elimina empresas cliente, configuración técnica
# y operación antes de volver a crear el seed local.
python manage.py migrate --noinput
python manage.py reset_to_security_baseline --yes
python manage.py seed_clean_demo_baseline --yes --reset-passwords
python manage.py reset_globaloil_flow --yes
python manage.py validate_globaloil_flow_seed
python manage.py check

echo "Base demo limpia reconstruida: seguridad, cuentas demo y flujo técnico local."
