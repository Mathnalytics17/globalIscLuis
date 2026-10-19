# RBAC: acciones, lugares y datos

El control de acceso se compone de dos decisiones independientes. Mantenerlas
separadas evita que otorgar acceso a una pantalla revele datos de empresas que
no corresponden al usuario.

## 1. Acceso a lugares y acciones

Los permisos con código `modulo.accion` controlan si el usuario puede abrir un
lugar y qué puede hacer allí. Por ejemplo:

- `reportes.ver` permite abrir la biblioteca de reportes.
- `reportes.generar`, `reportes.previsualizar`, `reportes.subir_firma` y
  `reportes.descargar_pdf` cubren el flujo técnico de generar un informe.
- `reportes.aprobar`, `reportes.publicar_cliente`, `reportes.enviar_email` y
  `reportes.anular` son decisiones de entrega y deben asignarse solo a quien
  tenga esa responsabilidad.
- `maquinas.ver` y `activos.ver` permiten consultar los módulos de activos;
  no son requisito para filtrar reportes.

La pantalla **Seguridad y accesos > Roles y permisos** edita estos permisos por
rol. Solo se muestran permisos activos. Los permisos retirados no se pueden
volver a asignar ni provocar un error al guardar.

## 2. Alcance de datos

El alcance determina *de qué empresas* se pueden leer o modificar datos una
vez que el permiso de la acción ya fue concedido. Se configura en el editor del
rol como **Datos que puede consultar**:

| Alcance | Resultado |
| --- | --- |
| Solo empresa del usuario | Solo la empresa asociada al usuario. |
| Todas las empresas | Datos de todos los clientes; adecuado para personal interno autorizado. |
| Empresas asignadas por usuario | Solo las empresas marcadas explícitamente para cada usuario. |
| Solo Global Oil | Solo los datos de Global Oil. |

En **Seguridad y accesos > Usuarios** se puede sobrescribir el alcance del rol
para un usuario concreto y, si se selecciona *Empresas asignadas*, escoger las
empresas autorizadas. La sobrescritura no cambia permisos: solo limita o amplía
los datos visibles para ese usuario.

## Perfil Laboratorista predeterminado

El perfil base del laboratorista cubre recepción de lotes, asignación y carga
de pruebas/resultados. Para cerrar el flujo de resultados a informe, debe
tener además `reportes.ver`, `reportes.generar`, `reportes.previsualizar`,
`reportes.subir_firma`, `reportes.descargar_pdf` y `reportes.ver_versiones`.
No recibe por defecto aprobación, publicación, envío ni anulación de informes;
esas acciones corresponden al revisor o a quien opere la entrega.

Los desplegables de Cliente, Equipo y Punto de medida en Reportes se generan
desde los reportes que ya están dentro de ese alcance de datos. Por tanto, un
laboratorista puede usarlos sin requerir permisos de administración de activos.
