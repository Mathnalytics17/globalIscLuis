[CmdletBinding()]
param(
    [string[]]$Reportes = @(
        "C:\Users\Usuario\Downloads\REGISTRO OA.xlsx",
        "C:\Users\Usuario\Downloads\REPORTES 2026 CORTO 20 SEPTIMBRE (1).xlsx"
    ),
    [string]$Conocimiento = "C:\Users\Usuario\Downloads\Base_Conocimiento_Aceites_v9.xlsx",
    [string]$Output = "",
    [switch]$Replace
)

$ErrorActionPreference = "Stop"
$etlScript = Join-Path $PSScriptRoot "etl_historica_global_oil.py"
if (-not $Output) {
    $Output = Join-Path $PSScriptRoot "..\outputs\migracion_historica_global_oil"
}

if (-not (Test-Path -LiteralPath $Reportes -PathType Leaf)) {
    throw "No se encontró el Excel de reportes: $Reportes"
}
if (-not (Test-Path -LiteralPath $Conocimiento -PathType Leaf)) {
    throw "No se encontró el Excel de conocimiento: $Conocimiento"
}

$arguments = @($etlScript)
foreach ($report in $Reportes) { $arguments += @("--reportes", $report) }
$arguments += @("--conocimiento", $Conocimiento, "--output", $Output)
if ($Replace) { $arguments += "--replace" }

& python @arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Artefactos ETL creados en: $Output"
