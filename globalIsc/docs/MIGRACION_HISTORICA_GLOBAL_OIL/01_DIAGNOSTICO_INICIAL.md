# Diagnostico inicial de fuentes

## Inventario

| Fuente | Estructura observada | Uso propuesto |
| --- | --- | --- |
| F-01: Reportes 2026 | Hoja `Reporte OA`, 708 registros con OA, fechas, cliente, equipo, lubricante, mediciones, comentarios y conclusion. Hoja `Hoja2` con clasificacion auxiliar de clientes. | Historico de muestras, mediciones, interpretaciones y datos maestros. |
| F-02: Base de conocimiento v9 | Limites de metales, viscosidad, degradacion, ISO 4406, repertorio, origenes de metales y notas tecnicas. | Reglas tecnicas versionadas; no reemplaza resultados historicos. |

## Hallazgos que condicionan la carga

1. La OA esta completa y no presenta duplicados en la fuente observada. Es la mejor llave externa inicial, pero el modelo actual de `Muestra` usa identificador interno `M...`; debe aprobarse donde guardar la OA y como garantizar unicidad.
2. Existen variantes de catalogos y textos: `Km`, `km`, `KM`; `SI`, `si`, `no`; y valores con tildes, espacios o grafias diferentes.
3. Los periodos de servicio contienen `DESCONOCIDO`, `N/A`, `NUEVO` y `#VALUE!`. No pueden convertirse a cero.
4. Hay equipo, placa y contacto no identificados. Un registro valido no debe crear una maquina o punto de muestreo ficticio.
5. Las mediciones no aplican en todos los tipos de lubricante. La ausencia de TBN, TAN, punto de chispa o ISO no debe interpretarse como cero.
6. Conclusiones y comentarios son evidencia historica. La base v9 puede servir a evaluaciones futuras, pero no debe reescribir la interpretacion original sin decision expresa.
7. Se detectaron fechas de toma posteriores a la fecha de revision inicial. Deben quedar en cuarentena hasta confirmar fecha, periodo o archivo de origen.

## Encaje confirmado con la plataforma local

La plataforma ya tiene `Empresa`, `Maquina`, `PuntoMuestreo`, `Lubricante`, `Muestra`, `PruebaMuestra`, `Resultado` y versiones de interpretacion. Tambien tiene previsualizacion de lotes Excel.

Ese flujo existente no se considera compatible con F-01 hasta comprobarlo contra el formato de reportes historicos. No se reutilizara ni modificara por suposicion.

## Decisiones pendientes de DATAIA / Global Oil

| ID | Decision | Alternativas que deben resolverse |
| --- | --- | --- |
| D-01 | Llave externa de OA | Campo dedicado con unicidad, o referencia externa auditable en datos adicionales. |
| D-02 | Identidad de cliente | Normalizar variantes a empresa existente, crear empresa, o conservar pendiente de homologacion. |
| D-03 | Equipo sin identificador | Crear solo muestra sin activo, asociar a activo existente, o enviar a cuarentena. |
| D-04 | Punto de muestreo | Regla para distinguir equipo, componente y punto a partir del texto disponible. |
| D-05 | Lubricante | Regla para separar fabricante, referencia, grado y especificacion cuando el texto no lo permita claramente. |
| D-06 | Valores bajo limite | Representacion de `<1`: texto original, limite de deteccion y valor numerico analitico. |
| D-07 | Fechas futuras o inconsistentes | Corregir con evidencia, conservar con alerta, o excluir de la carga inicial. |
| D-08 | Interpretacion historica | Ubicacion de conclusion y `COM_*`; confirmar que se cargan como legado y no como calculo vigente. |

## Politica de excepciones propuesta

| Estado | Significado | Ejemplos |
| --- | --- | --- |
| Cargable | Datos requeridos y relaciones suficientes. | OA unica, fecha valida y cliente homologado. |
| Cargable con advertencia | Reporte trazable con dato no indispensable ausente. | Sin periodo de servicio. |
| Cuarentena | Resolver la ambiguedad puede cambiar identidad o significado. | Cliente no homologable, fecha futura, `#VALUE!`. |
| Rechazado | No puede identificarse o incumple regla bloqueante aprobada. | OA duplicada incompatible o archivo corrupto. |
