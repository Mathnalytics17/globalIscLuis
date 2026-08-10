$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

python manage.py migrate --noinput
python manage.py reset_globaloil_flow --yes
python manage.py check

Write-Host "Base demostrativa de Global Oil reconstruida correctamente."
