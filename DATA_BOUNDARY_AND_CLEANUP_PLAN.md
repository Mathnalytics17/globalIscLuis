# Aislamiento de datos y saneamiento operativo

## Propósito

El sistema separa tres decisiones que no deben mezclarse:

1. **Permiso:** la acción que un rol puede realizar (`reportes.aprobar`,
   `muestras.ver`, etc.).
2. **Alcance de datos:** las empresas cuyos registros puede consultar o
   modificar el usuario.
3. **Audiencia o publicación:** si un resultado ya puede ser consultado por el
   cliente de la empresa.

Un permiso de reportes no publica un informe y un alcance sobre una empresa no
convierte a su administrador en personal interno del laboratorio.

## Regla de publicación de reportes

Un usuario con rol de audiencia **COMPANY** solamente puede leer un reporte si
cumple todas las condiciones siguientes:

- pertenece a una empresa dentro de su alcance;
- `visible_cliente=True`;
- tiene aprobación registrada (`fecha_aprobacion` y `usuario_aprobacion`);
- no está anulado.

Los usuarios internos y globales ven el trabajo no publicado únicamente dentro
de su alcance de datos. Esta regla se aplica en la consulta base del API de
reportes; por tanto cubre listado, tablero, detalle, PDF, versiones y las
operaciones que parten de esa consulta. No se confía en ocultar botones del
frontend para proteger información.

## Tendencias e informe

Hay dos decisiones distintas:

- **Ver tendencias aquí:** preferencia local de la pantalla de interpretación.
  No modifica datos ni el PDF.
- **Incluir tendencias en el informe PDF:** opción persistida de la
  interpretación (`graficas_activas`). Junto con las pruebas seleccionadas,
  define el contenido del siguiente reporte generado.

## Auditoría transversal requerida

Antes de una liberación se revisará cada recurso que lleva empresa directa o
indirectamente: lotes, muestras, máquinas, puntos, resultados, interpretaciones,
reportes, archivos, históricos y exportaciones. Para cada endpoint debe quedar
una prueba de estas cuatro situaciones:

| Actor | Alcance | Publicación esperada |
| --- | --- | --- |
| Administrador Global | Todas | Ve todos los estados |
| Personal interno | Asignadas o todas | Ve trabajo interno del alcance |
| Administrador de empresa | Su empresa | Solo informes publicados |
| Usuario de otra empresa | Ninguno | No recibe datos ni metadatos |

La revisión incluye búsquedas, filtros, conteos, archivos descargables, rutas
por identificador y acciones anidadas (por ejemplo, versiones de un reporte),
porque un filtro correcto en la tabla no sirve si una ruta secundaria omite la
misma política.

## Plan seguro para limpiar la base de datos

No se elimina información directamente desde una consola ni mediante una seed.
La limpieza requiere esta secuencia, con respaldo y simulación obligatorios.

1. **Inventario no destructivo.** Registrar conteos, empresas, usuarios,
   perfiles, roles, permisos, catálogos, lotes, muestras, resultados, reportes,
   archivos y referencias históricas. Marcar candidatos de demo por reglas
   explícitas, nunca solo por nombre.
2. **Respaldo restaurable.** Generar un `pg_dump` consistente, guardar hashes y
   comprobar una restauración en una base temporal.
3. **Contrato de preservación.** Confirmar por escrito qué se conserva: usuarios
   y contraseñas, roles, permisos, perfiles de empresa, catálogos técnicos,
   configuración de laboratorio, archivos y/o empresas. No se asume que una
   empresa llamada “Demo” sea desechable.
4. **Simulación.** Ejecutar un comando de limpieza en modo `--dry-run` que
   enumere los registros y archivos que borraría por tipo. El resultado se
   revisa antes de habilitar cualquier escritura.
5. **Ejecución transaccional.** Borrar solamente los conjuntos aprobados y sus
   dependencias usando el recolector de relaciones de Django, en una transacción
   y con una confirmación explícita de doble factor (por ejemplo,
   `--apply --confirm-cleanup <id-del-plan>`).
6. **Archivos.** Comparar referencias de base con media; eliminar archivos
   huérfanos solo después de confirmar que la base quedó consistente.
7. **Validación y reversión.** Ejecutar migraciones, pruebas de permisos,
   creación manual de lote/muestra/resultado/reporte y una restauración de
   ensayo del respaldo. Si falla alguna validación, restaurar el respaldo.

La primera entrega de esta operación será un inventario y `dry-run`, no un
borrado. Para pasar a la fase destructiva hace falta la lista de entidades que
el propietario desea conservar.

### Comando disponible en local

El comando `purge_operational_data` ya realiza la simulación y limpia únicamente
la operación de laboratorio: importaciones, eventos operativos, reportes,
versiones de interpretación, resultados, asignaciones de muestras, lotes y
muestras. Preserva usuarios, perfiles, roles, permisos, empresas, catálogos,
máquinas, puntos de muestreo y carpetas de activos.

```powershell
docker exec backend python manage.py purge_operational_data --dry-run
```

La ejecución real requiere `--yes`; no debe usarse hasta revisar el inventario.
La opción `--delete-files` es independiente y elimina firmas/reportes del medio
local, por lo que también requiere una revisión del respaldo.

### Restablecimiento a usuarios y RBAC solamente

Cuando se requiera una base completamente vacía para crear empresas y operación
desde la UI, se usa `reset_to_security_baseline`. Conserva únicamente cuentas,
roles, permisos y sus relaciones; elimina empresas, perfiles usuario–empresa,
alcances por empresa, activos, catálogos, operación, auditoría, sesiones y
tokens. Los usuarios conservados quedan sin empresa, sin alcance de datos y sin
ruta inicial personalizada. Los administradores con el rol legado `GLOBAL`
siguen teniendo acceso global para crear la primera empresa.

```powershell
# Inventario: nunca modifica la base
docker exec backend python manage.py reset_to_security_baseline --dry-run

# Respaldo PostgreSQL antes de confirmar (ajuste el nombre del contenedor si aplica)
docker exec postgres sh -lc 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" > /tmp/pre-security-reset.dump'
docker cp postgres:/tmp/pre-security-reset.dump ./backups/pre-security-reset.dump

# Solo después de verificar el respaldo:
docker exec backend python manage.py reset_to_security_baseline --yes
```

Para el servidor se debe desplegar primero el código que contiene el comando,
realizar el mismo `--dry-run`, descargar y validar el respaldo con
`pg_restore -l`, y ejecutar `--yes` durante una ventana de mantenimiento. El
comando no toca archivos de media; los medios se inventarían y se depuran en una
operación separada para no eliminar firmas de las cuentas preservadas.

### Base mínima para pruebas manuales

Después del restablecimiento se puede crear una base coherente sin datos
operativos mediante `seed_clean_demo_baseline`. Deja Global Oil como empresa
interna protegida con su administrador global y tres empresas cliente; cada
cliente recibe tres cuentas vinculadas a su perfil RBAC: administrador, consulta
y carga de muestras. No crea cuentas internas de laboratorio por defecto: se
invitan desde Seguridad a Global Oil para probar ese flujo. No crea activos,
catálogos, pruebas, lotes, muestras ni reportes.

```powershell
docker exec -e DEMO_DEFAULT_PASSWORD=123456789Admin backend `
  python manage.py seed_clean_demo_baseline --yes --reset-passwords
```

Las cuentas son `admin@globaloil.local`, y para cada dominio `minera`, `taller`
e `industria`: `admin@<dominio>.demo`, `consulta@<dominio>.demo` y
`muestras@<dominio>.demo`. Todas usan la contraseña configurada en
`DEMO_DEFAULT_PASSWORD`.

## Migración posterior

Para importar datos reales, se usará una zona de staging con identificadores
externos y una tabla de trazabilidad de importación. Cada lote importado se
validará contra las mismas reglas de creación manual (empresa, máquina, punto,
pruebas, resultados y estado), y solo después se promoverá a producción. Los
datos de demostración no se reutilizarán como plantilla de producción.
