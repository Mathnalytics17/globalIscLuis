<#
Rebuild Global Oil local data only through the public HTTP API.

Run a dry run first (the default).  -ResetLocal is intentionally accepted only
with -Apply because it clears local business data before the reproducible load.
The report-generation step follows the import flow and creates internal drafts
only: hidden from the customer and never approved or emailed.
#>
[CmdletBinding()]
param(
    [string]$Reportes = "C:\Users\Usuario\Downloads\REPORTES 2026 CORTO 20 SEPTIMBRE (1).xlsx",
    [string]$Conocimiento = "C:\Users\Usuario\Downloads\Base_Conocimiento_Aceites_v9 (1).xlsx",
    [string]$Email = "admin@globaloil.local",
    [string]$Password,
    [ValidateSet("all", "mineros")][string]$ClientScope = "all",
    [switch]$Apply,
    [switch]$ResetLocal,
    [switch]$SkipFinalVerification,
    [string]$BaseUrl = "http://localhost:8001"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $PSCommandPath
$projectRoot = Split-Path -Parent $scriptRoot
$backendRoot = Split-Path -Parent $projectRoot
$artifacts = "outputs\migracion_historica_global_oil"
$pythonExecutable = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonExecutable -and (Test-Path -LiteralPath "C:\ProgramData\anaconda3\python.exe")) {
    $pythonExecutable = "C:\ProgramData\anaconda3\python.exe"
}
if (-not $pythonExecutable) {
    throw "No se encontró Python. Instale Python 3 o agregue python al PATH antes de ejecutar la ETL."
}

function Invoke-EtlPython {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & $pythonExecutable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Falló: $pythonExecutable $($Arguments -join ' ')" }
}

if ($ResetLocal -and -not $Apply) {
    throw "-ResetLocal exige -Apply. La corrida en seco nunca borra la base local."
}
if ($Apply -and [string]::IsNullOrWhiteSpace($Password)) {
    $securePassword = Read-Host "Contraseña del administrador local" -AsSecureString
    $Password = [System.Net.NetworkCredential]::new("", $securePassword).Password
}

Push-Location $projectRoot
try {
    if ($ResetLocal) {
        Push-Location $backendRoot
        try {
            docker compose -p globaloil-local --env-file .env.local -f docker-compose.prod.yml -f docker-compose.local.yml exec -T web python manage.py reset_to_security_baseline --yes
            if ($LASTEXITCODE -ne 0) { throw "Falló el reinicio local; la ETL no continuará." }
        } finally { Pop-Location }
    }

    Invoke-EtlPython scripts\etl_historica_global_oil.py --reportes $Reportes --conocimiento $Conocimiento --output $artifacts --replace --client-scope $ClientScope
    Invoke-EtlPython scripts\etl_global_oil_domain.py --artifacts $artifacts
    Invoke-EtlPython scripts\build_technical_configuration_proposal.py --artifacts $artifacts
    Invoke-EtlPython scripts\build_api_result_payloads.py --artifacts $artifacts
    Invoke-EtlPython scripts\build_physical_result_payloads.py --artifacts $artifacts
    Invoke-EtlPython scripts\report_machine_history.py --artifacts $artifacts
    Invoke-EtlPython scripts\audit_com_legacy_rules.py --artifacts $artifacts

    $common = @("--artifacts", $artifacts, "--base-url", $BaseUrl)
    if (-not $Apply) {
        Invoke-EtlPython scripts\load_global_oil_via_api.py @common
        Invoke-EtlPython scripts\load_technical_catalogs_via_api.py @common
        Invoke-EtlPython scripts\load_compound_tests_via_api.py --base-url $BaseUrl
        Invoke-EtlPython scripts\load_physical_tests_via_api.py --base-url $BaseUrl
        Invoke-EtlPython scripts\configure_iso4406_limits_via_api.py @common
        Invoke-EtlPython scripts\configure_element_limits_via_api.py @common
        Invoke-EtlPython scripts\configure_degradation_limits_via_api.py @common
        Invoke-EtlPython scripts\configure_viscosity_limits_via_api.py @common
    Invoke-EtlPython scripts\configure_viscosity_40c_limits_via_api.py @common
    Invoke-EtlPython scripts\configure_viscosity_index_limits_via_api.py @common
    Invoke-EtlPython scripts\configure_flash_point_limits_via_api.py @common
    Invoke-EtlPython scripts\configure_foam_limits_via_api.py @common
    Invoke-EtlPython scripts\verify_limit_configuration_via_api.py @common
        Invoke-EtlPython scripts\load_historic_samples_via_api.py @common
        Write-Output "DRY RUN: las etapas dependientes (recepción, asignación y resultados) se ejecutan encadenadas únicamente con -Apply; no se genera ningún dato local."
        return
    }

    $auth = @("--apply", "--email", $Email, "--password", $Password)
    Invoke-EtlPython scripts\load_global_oil_via_api.py @common @auth
    Invoke-EtlPython scripts\load_technical_catalogs_via_api.py @common @auth
    Invoke-EtlPython scripts\load_compound_tests_via_api.py --base-url $BaseUrl @auth
    Invoke-EtlPython scripts\load_physical_tests_via_api.py --base-url $BaseUrl @auth
    Invoke-EtlPython scripts\configure_iso4406_limits_via_api.py @common @auth
    Invoke-EtlPython scripts\configure_element_limits_via_api.py @common @auth
    Invoke-EtlPython scripts\configure_degradation_limits_via_api.py @common @auth
    Invoke-EtlPython scripts\configure_viscosity_limits_via_api.py @common @auth
    Invoke-EtlPython scripts\configure_viscosity_40c_limits_via_api.py @common @auth
    Invoke-EtlPython scripts\configure_viscosity_index_limits_via_api.py @common @auth
    Invoke-EtlPython scripts\configure_flash_point_limits_via_api.py @common @auth
    Invoke-EtlPython scripts\configure_foam_limits_via_api.py @common @auth
    Invoke-EtlPython scripts\verify_limit_configuration_via_api.py @common @auth
    Invoke-EtlPython scripts\load_historic_samples_via_api.py @common @auth
    Invoke-EtlPython scripts\repair_historic_sample_dates_via_api.py @common @auth
    Invoke-EtlPython scripts\advance_compound_workflow_via_api.py @common @auth
    Invoke-EtlPython scripts\submit_compound_results_via_api.py @common @auth --sample-test-map "$artifacts\staging\oa_pruebas_muestra.json"
    Invoke-EtlPython scripts\invalidate_nondetect_compound_results_via_api.py @common @auth
    Invoke-EtlPython scripts\assign_physical_tests_via_api.py @common @auth
    # The bulk Excel endpoint can exceed its HTTP timeout on historical batches.
    # The shard runner stores a checkpoint after every form and is resumable.
    Invoke-EtlPython scripts\run_physical_api_shards.py
    Invoke-EtlPython scripts\advance_historical_reports_via_api.py @common @auth --resume
    if (-not $SkipFinalVerification) {
        Push-Location $backendRoot
        try {
            docker compose -p globaloil-local --env-file .env.local -f docker-compose.prod.yml -f docker-compose.local.yml exec -T web python manage.py verify_global_oil_import --artifacts "/usr/src/globalIsc/$artifacts"
            if ($LASTEXITCODE -ne 0) { throw "Falló la verificación final de importación." }
        } finally { Pop-Location }
    }
} finally {
    Pop-Location
}
