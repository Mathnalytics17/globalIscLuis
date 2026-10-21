# Reinicio completo de la base demo

Este procedimiento es para un entorno de demostración que se quiere iniciar desde cero. Destruye empresas cliente, usuarios cliente, configuración técnica, activos, lotes, resultados, interpretaciones, reportes y auditoría operativa. No lo ejecute sobre datos productivos que deban conservarse.

## Antes de ejecutar

1. Despliegue el commit que incluye las migraciones y los comandos de seed.
2. Cree y compruebe un respaldo restaurable de PostgreSQL.
3. Defina una contraseña temporal fuerte para las cuentas demo en `DEMO_DEFAULT_PASSWORD`; nunca la agregue al repositorio ni al historial de comandos compartido.

## Ejecución en el contenedor del backend

Desde el directorio de la aplicación dentro del contenedor:

```sh
export DEMO_DEFAULT_PASSWORD='cambie-esta-clave-por-una-segura'
sh scripts/bootstrap_clean_demo.sh
```

El script aplica las migraciones, conserva únicamente la línea base de seguridad/RBAC, recrea las cuentas demo y carga el mismo seed técnico que se usa localmente (`reset_globaloil_flow`). Termina ejecutando `manage.py check`.

Las cuentas quedan documentadas por el comando `seed_clean_demo_baseline`: administrador global `admin@globaloil.local` y, para `minera`, `taller` e `industria`, cuentas `admin`, `consulta` y `muestras` con el dominio `.demo`.

## Verificación posterior

1. Inicie sesión como administrador global.
2. Verifique las empresas demo y la configuración técnica.
3. Cree una máquina, punto de medición, lubricante, lote, muestra, resultado, revisión e informe; esos datos operativos no forman parte del seed base.
