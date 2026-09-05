#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_DIR}"
python manage.py migrate --noinput
python manage.py reset_globaloil_flow --yes
python manage.py check

echo "Base demostrativa de Global Oil reconstruida correctamente."
