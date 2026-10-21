$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

if ([string]::IsNullOrWhiteSpace($env:DEMO_DEFAULT_PASSWORD) -or $env:DEMO_DEFAULT_PASSWORD.Length -lt 12) {
    throw "Defina DEMO_DEFAULT_PASSWORD con al menos 12 caracteres antes de ejecutar el bootstrap."
}

# Reinicio completo y repetible para un entorno demo. No use este script sobre
# datos que deban conservarse: elimina empresas cliente, configuración técnica
# y operación antes de volver a crear el seed local.
python manage.py migrate --noinput
python manage.py reset_to_security_baseline --yes
python manage.py seed_clean_demo_baseline --yes --reset-passwords
python manage.py reset_globaloil_flow --yes
python manage.py check

Write-Host "Base demo limpia reconstruida: seguridad, cuentas demo y flujo técnico local."
