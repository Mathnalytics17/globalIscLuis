#!/usr/bin/env bash
# Linux companion to run_final_global_oil_etl.ps1. It never changes that Windows script.
# The scope is fixed to Mineros Aluvial S.A.S. and its BIC variant, and it
# never resets or deletes data.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$(cd "$PROJECT_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3}"
ENV_FILE="$BACKEND_DIR/.env"
BASE_URL=""
EMAIL="admin@globaloil.local"
REPORTES="$SCRIPT_DIR/REGISTRO OA.xlsx"
CONOCIMIENTO="$SCRIPT_DIR/Base_Conocimiento_Aceites_v9.xlsx"
# This name is required by the resumable physical-result runner.
ARTIFACTS="outputs/migracion_historica_global_oil"
APPLY=false
SKIP_FINAL_VERIFICATION=false

usage() {
  cat <<'EOF'
Uso: ./scripts/run_final_mineros_aluvial_etl.sh [opciones]

  --apply                    Escribe por la API de producción.
  --env-file RUTA            Archivo de entorno (predeterminado: ../.env).
  --email CORREO             Predeterminado: admin@globaloil.local.
  --base-url URL             Sobrescribe FRONTEND_URL del archivo de entorno.
  --python RUTA              Python con openpyxl y requests.
  --reportes RUTA            Excel REGISTRO OA.
  --conocimiento RUTA        Excel Base de Conocimiento.
  --skip-final-verification  Omite solo la verificación final.

Sin --apply solo genera artefactos y simulaciones, sin escribir en la base.
El alcance siempre es Mineros Aluvial S.A.S. y Mineros Aluvial S.A.S. BIC.
Este ejecutor no contiene ninguna operación de borrado o reinicio de datos.
EOF
}

die() { echo "Error: $*" >&2; exit 1; }
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=true ;;
    --email) EMAIL="${2:?Falta el correo}"; shift ;;
    --env-file) ENV_FILE="${2:?Falta el archivo de entorno}"; shift ;;
    --base-url) BASE_URL="${2:?Falta la URL}"; shift ;;
    --python) PYTHON="${2:?Falta la ruta de Python}"; shift ;;
    --reportes) REPORTES="${2:?Falta el Excel}"; shift ;;
    --conocimiento) CONOCIMIENTO="${2:?Falta el Excel}"; shift ;;
    --skip-final-verification) SKIP_FINAL_VERIFICATION=true ;;
    --help|-h) usage; exit 0 ;;
    *) die "Opción desconocida: $1" ;;
  esac
  shift
done

[[ -f "$REPORTES" ]] || die "No se encontró el Excel de reportes: $REPORTES"
[[ -f "$CONOCIMIENTO" ]] || die "No se encontró el Excel técnico: $CONOCIMIENTO"
[[ -f "$ENV_FILE" ]] || die "No se encontró el archivo de entorno: $ENV_FILE"
command -v "$PYTHON" >/dev/null 2>&1 || die "No se encontró Python: $PYTHON"
if [[ "$PYTHON" == */* ]]; then
  # Make the path absolute without resolving the venv's python symlink.  If
  # that final symlink is resolved, Python loses its virtual-environment prefix.
  PYTHON="$(cd "$(dirname "$PYTHON")" && pwd -P)/$(basename "$PYTHON")"
fi
"$PYTHON" -c 'import openpyxl, requests' 2>/dev/null || die "Instale las dependencias de globalIsc/requirements.txt en el Python indicado."

# Do not source the env file: it is configuration data, not executable shell
# input. FRONTEND_URL is the production API base through nginx.
if [[ -z "$BASE_URL" ]]; then
  BASE_URL="$(awk -F= '/^FRONTEND_URL=/{sub(/^[^=]*=/, ""); gsub(/^\"|\"$/, ""); print; exit}' "$ENV_FILE")"
fi
[[ -n "$BASE_URL" ]] || die "FRONTEND_URL no está definido en $ENV_FILE; use --base-url."

cd "$PROJECT_DIR"
"$PYTHON" scripts/etl_historica_global_oil.py --reportes "$REPORTES" --conocimiento "$CONOCIMIENTO" \
  --output "$ARTIFACTS" --replace --client-scope mineros
"$PYTHON" scripts/etl_global_oil_domain.py --artifacts "$ARTIFACTS"
"$PYTHON" scripts/build_technical_configuration_proposal.py --artifacts "$ARTIFACTS"
"$PYTHON" scripts/build_api_result_payloads.py --artifacts "$ARTIFACTS"
"$PYTHON" scripts/build_physical_result_payloads.py --artifacts "$ARTIFACTS"
"$PYTHON" scripts/report_machine_history.py --artifacts "$ARTIFACTS"
"$PYTHON" scripts/audit_com_legacy_rules.py --artifacts "$ARTIFACTS"

COMMON=(--artifacts "$ARTIFACTS" --base-url "$BASE_URL")
if [[ "$APPLY" == false ]]; then
  "$PYTHON" scripts/load_global_oil_via_api.py "${COMMON[@]}"
  "$PYTHON" scripts/load_technical_catalogs_via_api.py "${COMMON[@]}"
  "$PYTHON" scripts/load_compound_tests_via_api.py --base-url "$BASE_URL"
  "$PYTHON" scripts/load_physical_tests_via_api.py --base-url "$BASE_URL"
  for script in configure_iso4406_limits_via_api.py configure_element_limits_via_api.py configure_degradation_limits_via_api.py configure_viscosity_limits_via_api.py configure_viscosity_40c_limits_via_api.py configure_viscosity_index_limits_via_api.py configure_flash_point_limits_via_api.py configure_foam_limits_via_api.py verify_limit_configuration_via_api.py load_historic_samples_via_api.py; do
    "$PYTHON" "scripts/$script" "${COMMON[@]}"
  done
  echo "SIMULACIÓN COMPLETA: no se escribieron datos. Revise $ARTIFACTS/{homologacion,qa,reports}."
  exit 0
fi

read -r -s -p "Contraseña de $EMAIL: " PASSWORD
echo
[[ -n "$PASSWORD" ]] || die "No se recibió contraseña."
AUTH=(--apply --email "$EMAIL" --password "$PASSWORD")
"$PYTHON" scripts/load_global_oil_via_api.py "${COMMON[@]}" "${AUTH[@]}"
"$PYTHON" scripts/load_technical_catalogs_via_api.py "${COMMON[@]}" "${AUTH[@]}"
"$PYTHON" scripts/load_compound_tests_via_api.py --base-url "$BASE_URL" "${AUTH[@]}"
"$PYTHON" scripts/load_physical_tests_via_api.py --base-url "$BASE_URL" "${AUTH[@]}"
for script in configure_iso4406_limits_via_api.py configure_element_limits_via_api.py configure_degradation_limits_via_api.py configure_viscosity_limits_via_api.py configure_viscosity_40c_limits_via_api.py configure_viscosity_index_limits_via_api.py configure_flash_point_limits_via_api.py configure_foam_limits_via_api.py verify_limit_configuration_via_api.py load_historic_samples_via_api.py repair_historic_sample_dates_via_api.py advance_compound_workflow_via_api.py; do
  "$PYTHON" "scripts/$script" "${COMMON[@]}" "${AUTH[@]}"
done
"$PYTHON" scripts/submit_compound_results_via_api.py "${COMMON[@]}" "${AUTH[@]}" --sample-test-map "$ARTIFACTS/staging/oa_pruebas_muestra.json"
"$PYTHON" scripts/invalidate_nondetect_compound_results_via_api.py "${COMMON[@]}" "${AUTH[@]}"
"$PYTHON" scripts/assign_physical_tests_via_api.py "${COMMON[@]}" "${AUTH[@]}"
"$PYTHON" scripts/run_physical_api_shards.py --artifacts "$ARTIFACTS" --base-url "$BASE_URL" --email "$EMAIL"
"$PYTHON" scripts/advance_historical_reports_via_api.py "${COMMON[@]}" "${AUTH[@]}" --resume

if [[ "$SKIP_FINAL_VERIFICATION" == false ]]; then
  cd "$BACKEND_DIR"
  ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml \
    exec -T web python manage.py verify_global_oil_import --artifacts "/usr/src/globalIsc/$ARTIFACTS"
fi
echo "IMPORTACIÓN COMPLETA: Mineros Aluvial; los reportes quedan internos y sin publicar."
