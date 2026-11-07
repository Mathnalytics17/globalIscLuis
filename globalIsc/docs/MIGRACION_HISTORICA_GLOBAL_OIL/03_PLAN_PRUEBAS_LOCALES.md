# Plan de pruebas locales

## Proposito

Permitir que DATAIA pruebe cada hito antes de aprobar el siguiente. Estas pruebas son reproducibles en el entorno local y no requieren produccion.

## Preparacion local

Desde `backend`, levantar el ambiente local documentado por el proyecto:

```powershell
docker compose -p globaloil-local --env-file .env.local -f docker-compose.prod.yml -f docker-compose.local.yml up -d --build web daphne
```

No se deben usar credenciales, bases ni el archivo `.env` de produccion. Antes de cada prueba de carga se toma un respaldo de la base local o se crea una base limpia.

## Pruebas por hito

| ID | Hito | Accion verificable por DATAIA | Resultado esperado | Evidencia |
| --- | --- | --- | --- | --- |
| P-01 | Fuente inmovilizada | Comparar nombre, tamano y hash de F-01/F-02 contra el inventario. | Se prueba exactamente la fuente aprobada. | Registro de fuente. |
| P-02 | Diagnostico | Revisar conteos, campos y hallazgos en `01_DIAGNOSTICO_INICIAL.md`. | Hallazgos aceptados o devueltos con observacion. | Aprobacion escrita. |
| P-03 | Homologacion | Elegir diez OAs de distintos tipos y revisar cada mapeo. | La regla no pierde ni cambia significado. | Matriz aprobada y muestra anotada. |
| P-04 | Normalizacion | Comparar origen y valor preparado para unidades, catalogos y fechas. | Cada cambio conserva valor original y razon. | Reporte de transformacion. |
| P-05 | Cuarentena | Probar `DESCONOCIDO`, `#VALUE!`, `<1` y fechas inconsistentes. | No crea entidades ficticias ni convierte a cero. | Reporte de excepciones. |
| P-06 | Piloto | Cargar lote representativo en una base local limpia. | Se consultan muestra, activo, lubricante, pruebas, resultados e interpretacion. | Bitacora de ejecucion. |
| P-07 | Idempotencia | Ejecutar dos veces el mismo piloto. | La segunda ejecucion no duplica registros ni resultados. | Comparacion de conteos. |
| P-08 | Recuperacion | Restaurar respaldo anterior al piloto. | La base vuelve al estado previo. | Registro de restauracion. |
| P-09 | Carga completa | Ejecutar sobre copia local aprobada. | Los conteos concilian y cada excepcion tiene causa. | Informe de validacion. |

## Casos minimos del piloto

- Un reporte de motor diesel y uno de motor gasolina.
- Un reporte hidraulico, uno de engranaje, uno de transmision y uno de diferencial.
- Una muestra sin periodo de servicio.
- Una medicion bajo limite (`<1`).
- Un equipo o placa desconocidos.
- Una conclusion con comentarios multiples.
- Un registro que deba ir a cuarentena.

## Criterios de aprobacion tecnica del piloto

1. Cada OA piloto es localizable desde su referencia externa.
2. No hay duplicados despues de repetir la ejecucion.
3. Las mediciones conservan nombre, valor, unidad y fecha de origen.
4. Las conclusiones historicas permanecen identificadas como legado.
5. Los registros problematicos no se ocultan: aparecen en cuarentena o rechazo.
6. La restauracion local funciona antes de autorizar la carga completa.

## Limitacion actual

El proyecto tiene una vista previa para lotes de muestras Excel. Este plan exige probar su compatibilidad antes de reutilizarlo. Hasta entonces, no se considera mecanismo de migracion de los reportes historicos.
