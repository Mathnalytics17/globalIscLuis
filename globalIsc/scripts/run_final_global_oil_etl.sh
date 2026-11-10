#!/usr/bin/env bash
# Rebuild a historical Global Oil load inside the backend container.
# The caller must first copy both workbooks to paths visible in this container.
set -euo pipefail

REPORTES="/tmp/REGISTRO_OA.xlsx"
CONOCIMIENTO="/tmp/Base_Conocimiento_Aceites_v9.xlsx"
BASE_URL="http://localhost:8000"
EMAIL=""
PASSWORD_ENV="GO_PASSWORD"
CLIENT_SCOPE="mineros"
APPLY=false

usage() {
  cat <<'USAGE'
Usage:
  run_final_global_oil_etl.sh --apply --email EMAIL [options]

Options:
  --reportes PATH          Workbook REGISTRO OA inside the container.
  --conocimiento PATH      Workbook Base de Conocimiento inside the container.
  --base-url URL           URL served by this same deployment.
  --email EMAIL            Existing administrator email for the API.
  --password-env NAME      Environment variable containing its password (GO_PASSWORD by default).
  --client-scope SCOPE     mineros (default) or all.
  --apply                  Required: writes through the public API.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reportes) REPORTES="$2"; shift 2 ;;
    --conocimiento) CONOCIMIENTO="$2"; shift 2 ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    --email) EMAIL="$2"; shift 2 ;;
    --password-env) PASSWORD_ENV="$2"; shift 2 ;;
    --client-scope) CLIENT_SCOPE="$2"; shift 2 ;;
    --apply) APPLY=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Opción desconocida: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ "$APPLY" == true ]] || { echo "Use --apply para una carga real." >&2; exit 2; }
[[ -n "$EMAIL" ]] || { echo "Falta --email." >&2; exit 2; }
[[ -f "$REPORTES" ]] || { echo "No existe el Excel de reportes: $REPORTES" >&2; exit 2; }
[[ -f "$CONOCIMIENTO" ]] || { echo "No existe el Excel de conocimiento: $CONOCIMIENTO" >&2; exit 2; }

PASSWORD="${!PASSWORD_ENV:-}"
[[ -n "$PASSWORD" ]] || { echo "No existe la variable de contraseña $PASSWORD_ENV." >&2; exit 2; }

cd "$(dirname "$0")/.."
ARTIFACTS="outputs/migracion_historica_global_oil"
AUTH=(--apply --email "$EMAIL" --password "$PASSWORD")
COMMON=(--artifacts "$ARTIFACTS" --base-url "$BASE_URL")

run() { python "$@"; }

run scripts/etl_historica_global_oil.py --reportes "$REPORTES" --conocimiento "$CONOCIMIENTO" --output "$ARTIFACTS" --replace --client-scope "$CLIENT_SCOPE"
run scripts/etl_global_oil_domain.py --artifacts "$ARTIFACTS"
run scripts/build_technical_configuration_proposal.py --artifacts "$ARTIFACTS"
run scripts/build_api_result_payloads.py --artifacts "$ARTIFACTS"
run scripts/build_physical_result_payloads.py --artifacts "$ARTIFACTS"
run scripts/report_machine_history.py --artifacts "$ARTIFACTS"
run scripts/audit_com_legacy_rules.py --artifacts "$ARTIFACTS"

run scripts/load_global_oil_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/load_technical_catalogs_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/load_compound_tests_via_api.py --base-url "$BASE_URL" "${AUTH[@]}"
run scripts/load_physical_tests_via_api.py --base-url "$BASE_URL" "${AUTH[@]}"
run scripts/configure_iso4406_limits_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/configure_element_limits_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/configure_degradation_limits_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/configure_viscosity_limits_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/configure_viscosity_40c_limits_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/configure_viscosity_index_limits_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/configure_flash_point_limits_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/configure_foam_limits_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/verify_limit_configuration_via_api.py "${COMMON[@]}" "${AUTH[@]}"

run scripts/load_historic_samples_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/repair_historic_sample_dates_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/advance_compound_workflow_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/submit_compound_results_via_api.py "${COMMON[@]}" "${AUTH[@]}" --sample-test-map "$ARTIFACTS/staging/oa_pruebas_muestra.json"
run scripts/invalidate_nondetect_compound_results_via_api.py "${COMMON[@]}" "${AUTH[@]}"
run scripts/assign_physical_tests_via_api.py "${COMMON[@]}" "${AUTH[@]}"

export DATAIA_IMPORT_PASSWORD="$PASSWORD"
run scripts/run_physical_api_shards.py --password-env DATAIA_IMPORT_PASSWORD
unset DATAIA_IMPORT_PASSWORD

run scripts/advance_historical_reports_via_api.py "${COMMON[@]}" "${AUTH[@]}" --resume
python manage.py verify_global_oil_import --artifacts "$ARTIFACTS"
