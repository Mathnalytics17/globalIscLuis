# Importación del Diario de Laboratorio 2024

Fuente: `2024 - CCF-PI-F-013-V2-Diario de Laboratorio-Externas (2).xlsx`,
hoja `Listado`.

## Alcance ejecutado

Destino: **Mineros S.A**. El archivo identifica al cliente como `MINEROS
ALUVIAL S.A.S`; no se creó ni se modificó ninguna empresa, muestra, lote ni
resultado.

- 320 filas válidas leídas.
- 36 lubricantes creados.
- 63 máquinas creadas.
- 183 puntos de medida creados.
- 5 filas omitidas por tener equipo o lubricante marcado como desconocido/no
  aplicable.

## Criterio de clasificación

Los nombres que contienen `DRAGA`, `UG`, `EXCAVADORA` o `LANCHA` se agruparon
por activo. El resto conserva el nombre de equipo del archivo como máquina.
Cada punto usa el lubricante más frecuente encontrado para esa combinación.
La frecuencia de cambio solo se establece cuando el campo de periodo trae un
valor horario válido; no se infiere una frecuencia de análisis.

El script reproducible es `scripts/import_lab_assets.py` y no procesa tablas de
muestras, lotes ni resultados.

## Sincronización con el árbol de activos

Una máquina aparece en el árbol solamente cuando tiene un nodo `Carpeta` de
tipo `machine` enlazado por su campo `machine`. La empresa ya tiene su propia
carpeta raíz, por lo que la sincronización no creó carpetas de clasificación
adicionales: cada máquina quedó directamente debajo de la raíz de **Mineros
S.A**. Los puntos de medida se muestran como hijos de su máquina.

Verificación posterior a la importación y sincronización:

- 67 máquinas activas de Mineros S.A y 67 nodos de máquina enlazados.
- 0 máquinas activas sin representación en el árbol.
- 186 puntos de medida y 38 lubricantes en el catálogo global.

Desde la vista Árbol de activos se pueden crear o mover las carpetas padre que
se necesiten y reorganizar esas máquinas sin alterar sus puntos de medida ni
su historial.

## Catálogo global al crear puntos desde el árbol

El modal **Nuevo punto de muestreo** usa el mismo catálogo global de
lubricantes que la edición de máquinas y la recepción de muestras. Permite
seleccionar cualquier lubricante registrado o crear uno nuevo indicando
**fabricante** y **referencia / marca**; este queda disponible para todas las
empresas y asignado al punto.
No se captura un nombre libre de lubricante. Los textos libres que existían en
puntos históricos se muestran solo como referencia hasta que se les asigne un
elemento del catálogo.

## Raíces del árbol

No existe una acción manual de sincronización. Al crear o renombrar una empresa
el sistema crea o actualiza automáticamente su carpeta raíz; además, la consulta
del árbol reconcilia las empresas activas creadas antes de esta regla. Así el
árbol siempre parte de la información del sistema.
