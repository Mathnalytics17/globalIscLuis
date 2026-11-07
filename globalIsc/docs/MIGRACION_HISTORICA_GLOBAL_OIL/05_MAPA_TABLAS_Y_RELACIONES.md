# Mapa de tablas y relaciones del destino

## Estado de este inventario

Este documento se elaboro leyendo los modelos y migraciones actuales del backend en la rama `feature/migracion-historica-global-oil`. Es el mapa de diseno para la migracion.

**Verificado el 28 de octubre de 2026 en PostgreSQL local:** Django reconoce 64 modelos, no hay migraciones pendientes, `manage.py check` no reporta incidencias y `GET /api/health/` responde `200` con base de datos disponible.

Los nombres fisicos de tabla quedaron comprobados. El inventario de valores existentes en catalogos y maestros sigue pendiente y se hace antes de mapear los Excel.

## Cadena operativa principal

```text
Empresa -> Maquina -> PuntoMuestreo
                    \-> Lubricante (catalogo global)

Empresa -> LoteMuestras -> Muestra -> PruebaMuestra -> Resultado
                             |              \-> configuracion y limites
                             |-> MuestraAtributoTecnico
                             |-> VersionInterpretacion -> Reporte -> ReporteEnvio
                             \-> AsignacionPuntoMuestreo -> PuntoMuestreo

CorridaImportacion y EventoAuditoriaOperativa registran la evidencia de la migracion.
```

## Tablas centrales para el historico

| Tabla o modelo | Relacion relevante | Uso en la migracion | Decision actual |
| --- | --- | --- | --- |
| `misc.Empresa` | Padre de maquinas y lotes. | Cliente homologado de cada OA. | Reutilizar; no crear por coincidencia aproximada. |
| `activesTree.Maquina` | Pertenece a una empresa. | Activo o equipo identificado en el reporte. | Reutilizar o crear solo bajo regla aprobada. |
| `activesTree.PuntoMuestreo` | Pertenece a una maquina y puede enlazar lubricante. | Punto o componente de toma. | Pendiente D-04. |
| `activesTree.Lubricante` | Catalogo global; puede enlazar puntos. | Lubricante homologado. | Pendiente D-05. |
| `muestras.LoteMuestras` | Agrupa muestras y pertenece opcionalmente a empresa. | Contenedor operativo si el historico debe conservar lotes. | Pendiente definir criterio de lote historico. |
| `muestras.Muestra` | Puede pertenecer a lote y referir maquina. | Nucleo de cada reporte historico. | Reutilizar. Debe resolverse D-01 para la OA externa. |
| `activesTree.AsignacionPuntoMuestreo` | Une muestra y punto. | Asociacion posterior y auditable al punto de muestreo. | Reutilizar cuando exista punto confiable. |
| `muestras.MuestraAtributoTecnico` | Une muestra con catalogo, campo e item. | Tipo, grado, especificacion y otros atributos normalizados. | Reutilizar para catalogos aprobados. |
| `muestras.PruebaMuestra` | Une muestra y prueba; es unica por muestra y prueba. | Resultado de cada parametro analitico. | Reutilizar; definir catalogo de pruebas. |
| `resultado.Resultado` | Depende de `PruebaMuestra`. | Resultado especializado cuando aplique al flujo actual. | Validar si se usa junto o en lugar de los campos de `PruebaMuestra`. |
| `resultado.VersionInterpretacion` | Pertenece a muestra. | `COM_*`, conclusion y comentarios conservados como legado. | Reutilizar con origen `legado`. |
| `reporte.Reporte` | Pertenece a muestra y referencia interpretacion. | Reporte emitido o snapshot historico, si se aprueba crear uno por OA. | Pendiente separar OA de consecutivo interno de reporte. |
| `muestras.CorridaImportacion` | Se asocia opcionalmente a empresa y actor. | Trazabilidad de cada corrida: checksum, conteos, advertencias y errores. | Reutilizar; ya existe para este objetivo. |
| `muestras.EventoAuditoriaOperativa` | Puede enlazar empresa, lote, muestra, prueba, reporte, maquina y punto. | Evidencia por cada evento importante de migracion. | Reutilizar. |

## Catalogos y reglas tecnicas existentes

| Grupo | Modelos principales | Aporte de `Base_Conocimiento_Aceites_v9` |
| --- | --- | --- |
| Definicion de pruebas | `misc.Prueba`, `PruebaResultado`, `PruebaResultadoDivision`, `PruebaResultadoComponente`, `PruebaResultadoDisposicion`, `PruebaResultadoDisposicionItem` | Parametros y estructura de mediciones. |
| Catalogos versionados | `CatalogoTecnico`, `CatalogoTecnicoVersion`, `CatalogoTecnicoCampo`, `CatalogoTecnicoItem`, `CatalogoTecnicoItemValor` | Tipo de uso, viscosidad, especificacion y limites por catalogo. |
| Escalas y limites | `EscalaComparacion`, `EscalaComparacionItem`, `PruebaFuenteLimite`, `CriterioEvaluacionLimite`, `PruebaLimiteCampo`, `PruebaFuenteCatalogo`, `CriterioCatalogoSeleccion` | Limites de metales, ISO 4406, degradacion y criterios de evaluacion. |
| Configuracion de laboratorio | `EquipoPrueba`, `MetodoEquipo`, `Condicion`, `Unidad`, `LotePruebasPredefinido`, `LotePruebasPredefinidoDetalle`, `TipoGestionMuestra` | Unidades, metodos y configuracion operacional. |

## Tablas de soporte que no reciben contenido del Excel directamente

| Grupo | Modelos | Tratamiento |
| --- | --- | --- |
| Historial | `HistorialMuestra`, `HistoricoResultado`, `RevisionResultado`, `ReporteEnvio` | Solo se crean si el proceso de migracion necesita dejar una accion auditable; no se reconstruye historia inexistente. |
| Seguridad y acceso | `users.User`, perfiles, roles, permisos, alcances, invitaciones y bitacora de usuario. | No se crea un usuario por cada nombre de responsable del Excel. |
| Arbol visual | `activesTree.Carpeta` | No se altera por la migracion. Los activos y puntos usan el flujo existente de sincronizacion. |
| Tokens de importacion Excel | `SampleBatchExcelTemplateToken` | No se usa hasta probar si el formato actual admite los reportes historicos. |

## Inventario fisico completo verificado

| Grupo | Tablas |
| --- | --- |
| Activos | `activesTree_asignacionpuntomuestreo`, `activesTree_carpeta`, `activesTree_lubricante`, `activesTree_maquina`, `activesTree_puntomuestreo` |
| Operacion de muestras | `muestras_corridaimportacion`, `muestras_eventoauditoriaoperativa`, `muestras_historialmuestra`, `muestras_ingresolablote`, `muestras_lotemuestras`, `muestras_muestra`, `muestras_muestraatributotecnico`, `muestras_pruebamuestra`, `muestras_samplebatchexceltemplatetoken` |
| Resultados y reportes | `resultado_historicoresultado`, `resultado_resultado`, `resultado_revisionresultado`, `resultado_versioninterpretacion`, `reporte_reporte`, `reporte_reporteenvio` |
| Empresas y configuracion tecnica | `misc_empresa`, `misc_tipogestionmuestra`, `misc_equipoprueba`, `misc_metodoequipo`, `misc_condicion`, `misc_categoriaunidad`, `misc_unidad`, `misc_lotepruebaspredefinido`, `misc_lotepruebaspredefinidodetalle` |
| Pruebas de laboratorio | `misc_prueba`, `misc_pruebaresultado`, `misc_pruebaresultadodivision`, `misc_pruebaresultadocomponente`, `misc_pruebaresultadoseparador`, `misc_pruebaresultadodisposicion`, `misc_pruebaresultadodisposicionitem` |
| Catalogos y limites | `misc_catalogotecnico`, `misc_catalogotecnicoversion`, `misc_campotecnicomuestra`, `misc_catalogotecnicocampo`, `misc_catalogotecnicoitem`, `misc_catalogotecnicoitemvalor`, `misc_escalacomparacion`, `misc_escalacomparacionitem`, `misc_pruebafuentelimite`, `misc_criterioevaluacionlimite`, `misc_pruebafuentecatalogo`, `misc_criteriocatalogoseleccion`, `misc_pruebalimitecampo` |
| Usuarios y seguridad | `users_user`, `users_emailverificationtoken`, `users_passwordresettoken`, `users_securityrole`, `users_securitypermission`, `users_securityrolepermission`, `users_usercompanyprofile`, `users_userdatascopecompany`, `users_userinvitation`, `users_userauditlog` |
| Django interno | `django_admin_log`, `auth_group`, `auth_permission`, `django_content_type`, `django_session` |

## Restricciones que condicionan el mapeo

1. `PruebaMuestra` permite una sola prueba de cada tipo por muestra. La identificacion de cada columna analitica debe apuntar a una `Prueba` unica y aprobada.
2. `Muestra` genera su propio identificador interno. La OA del Excel no debe sustituirlo sin una decision de diseno y migracion explicita.
3. `Reporte` genera un consecutivo interno y limita la version por muestra. La OA fuente y el consecutivo de reporte son conceptos distintos.
4. Los catalogos y fuentes de limite ya contemplan versionamiento. La base v9 debe entrar como una version trazable, no como una sobreescritura silenciosa.
5. `CorridaImportacion` ya soporta checksum, conteos, advertencias, errores y reversibilidad. Es la bitacora obligatoria propuesta para cada ejecucion.

## Primer resultado de arquitectura

La estrategia inicial es **adaptarse al modelo actual**. No se propone cambiar la pagina ni crear entidades nuevas antes de completar el mapeo. La unica posible brecha de modelo identificada hasta ahora es una referencia externa de OA unica y consultable; se evaluara despues de completar D-01 y no se implementara sin aprobacion.

## Siguiente secuencia

1. Levantar el ambiente local y verificar este inventario contra Django y PostgreSQL.
2. Inventariar los valores ya existentes en empresas, maquinas, puntos, lubricantes, pruebas, unidades y catalogos.
3. Revisar los dos Excel columna por columna contra este mapa.
4. Completar la matriz de homologacion con destino, regla y estado de cada campo.
5. Solo entonces decidir si hace falta una migracion de esquema o basta con procesos de backend.
