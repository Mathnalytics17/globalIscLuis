# Pruebas de aceptación: trazabilidad y cargas

Ejecute estas pruebas con una cuenta global y, cuando se indique, con una
cuenta de empresa. No use datos productivos para la primera ronda.

## 1. Línea de tiempo de operación

1. Cree un lote y una muestra; abra el detalle del lote.
2. Edite la muestra, asígnele un punto, asigne pruebas y registre resultados.
3. Corrija un resultado indicando motivo; invalide y reactive una muestra.
4. Revise, interprete y genere un reporte.
5. En **Actividad y trazabilidad** del lote confirme actor, hora, acción,
   motivo y antes/después para cada paso.

Resultado esperado: no se elimina evidencia al corregir, invalidar o reabrir.

## 2. Activos, puntos y tendencias

1. Cree o edite una máquina y un punto de medición; cambie lubricante o
   frecuencia.
2. En la ficha de máquina confirme la actividad reciente.
3. En Árbol de activos, menú del punto, abra **Ver actividad del punto**.
4. En `/machines/historico`, filtre empresa, máquina, punto y prueba.
5. Pruebe el paginador y active **Incluir muestras invalidadas**.

Resultado esperado: el histórico se consulta por máquina en el servidor y las
invalidadas solo aparecen con la marca explícita.

## 3. Configuración técnica

1. Cree una versión posterior de un límite y modifique un campo o criterio.
2. En Configuración técnica > Límites expanda la prueba y pulse **Comparar**.
3. Cree una versión de catálogo, cambie/agregue/retire un ítem y pulse
   **Comparar** desde Configuración técnica > Catálogos.

Resultado esperado: la pantalla enumera cambios legibles; no muestra el JSON
interno como interfaz principal.

## 4. Módulo central

1. Abra `/trazabilidad` con administrador global.
2. Busque por código de lote, muestra o texto de motivo; pruebe entidad,
   origen y **Solo cambios críticos**.
3. Abra una acción para revisar sus valores antes y después.
4. Inicie sesión como administrador o consulta de una empresa y repita.

Resultado esperado: el usuario de empresa no ve eventos de otra empresa, aun
si intenta cambiar parámetros en la URL.

## 5. Prevalidación Excel y corrida de importación

1. Descargue una plantilla Excel y complete una fila correcta y otra con un
   error deliberado.
2. Use la previsualización de importación.
3. Verifique que la respuesta incluya `import_run_id` y que en
   `/api/lubrication/import-runs/` exista una corrida con archivo, checksum,
   filas, errores y detalle de errores.
4. Repita con archivo completamente válido: el estado debe ser `validada`.

Resultado esperado: la prevalidación deja evidencia aun cuando el archivo no
pueda aplicarse. La aplicación masiva definitiva debe usar esa corrida como
referencia y actualizarla a `aplicada`, `parcial` o `revertida`.

## Validación técnica

Antes de desplegar: `python manage.py migrate`, `python manage.py check` y
`npm run lint`. No se requiere construir el frontend como parte de esta guía.
