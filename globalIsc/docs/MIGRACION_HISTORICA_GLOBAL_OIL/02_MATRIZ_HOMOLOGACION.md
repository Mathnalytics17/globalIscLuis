# Matriz de homologacion propuesta

Esta matriz es de diseno. Las filas marcadas **Pendiente** no se aplican hasta que DATAIA las apruebe.

## Entidades y campos principales

| Fuente F-01 | Destino propuesto | Transformacion | Estado |
| --- | --- | --- | --- |
| `OA` | Referencia externa de la muestra | Conservar texto y exigir unicidad. No reemplaza el identificador interno de `Muestra`. | Pendiente D-01 |
| `FECHA TOMA DE MUESTRA` | `Muestra.fecha_toma` | Fecha valida con zona horaria definida para el ambiente. | Aprobable |
| `CONTACTO` | `Muestra.contacto_cliente` | Conservar texto de origen; no inferir que es persona. | Aprobable |
| `PLACA` | `Muestra.equipo_placa` y/o identificador de `Maquina` | Normalizar espacios y mayusculas sin inventar identificadores. | Pendiente D-03 |
| `EQUIPO` | `Maquina.nombre` / `PuntoMuestreo.nombre` | Separar activo y componente solo con regla aprobada. | Pendiente D-04 |
| `CLIENTE` | `Empresa.nombre` | Homologar mediante catalogo aprobado y guardar texto original. | Pendiente D-02 |
| `LUBRICANTE` | `Lubricante.nombre` | Conservar texto; extraer fabricante y referencia solo si es inequivoco. | Pendiente D-05 |
| `PERIODO DE SERVICIO` y unidad | Periodo de aceite de `Muestra` | Convertir solo numeros validos y unidad normalizada. Textos ambiguos quedan como evidencia o excepcion. | Aprobable |
| `PERIODO DE SERVICIO EQUIPO` y unidad | Periodo de equipo de `Muestra` | Igual que el periodo de aceite. | Aprobable |
| Viscosidad, metales, agua, TBN, TAN y demas mediciones | `PruebaMuestra` + `Resultado` | Una medicion por prueba aplicable; preservar valor fuente y fecha de medicion. | Pendiente catalogo de pruebas |
| `COM_*` | Version de interpretacion historica | Conservar como veredicto legado; no recalcular. | Pendiente D-08 |
| `CONCLUSION`, `COM_1` a `COM_10` | Version de interpretacion / observaciones | Conservar texto y orden original. | Pendiente D-08 |
| `Tipo`, `Viscosidad`, `Esp_Cal` | Metadatos tecnicos de muestra o lubricante | Normalizar contra catalogos con trazabilidad de origen. | Pendiente |
| `Responsable` | Referencia de analista historico | Mapear solo a usuario existente y autorizado; de lo contrario conservar como texto de legado. | Pendiente |

## Reglas innegociables de transformacion

1. El dato original debe ser recuperable para cada dato transformado.
2. Un vacio, un cero, un valor no aplicable y un dato desconocido son estados distintos.
3. Los valores `<n` no se convierten a `n` ni a cero.
4. Las reglas tecnicas v9 se versionan; no modifican automaticamente las conclusiones historicas.
5. No se crean empresas, maquinas, puntos, lubricantes o usuarios por simple similitud de texto sin regla aprobada.
6. Toda fila no procesada se conserva en un reporte de excepciones con OA y causa.

## Catalogos iniciales a homologar

- Empresas y variantes de nombre.
- Equipos, placas, componentes y puntos de muestreo.
- Lubricantes, grados de viscosidad, especificaciones y tipo de uso.
- Unidades de periodo: horas, kilometros, millas y dias.
- Pruebas analiticas y unidades de resultado.
- Estados de evaluacion y origen de interpretacion.
