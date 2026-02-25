# Matriz RBAC v1 - TCeMPEI

## Roles
- admin
- analyst
- reviewer
- viewer

## Leyenda
- C: crear
- R: consultar
- U: actualizar
- D: eliminar (soft delete)
- A: aprobar
- HD: hard delete con motivo

## Matriz de permisos
| Recurso/Accion | admin | analyst | reviewer | viewer |
|---|---|---|---|---|
| Usuarios | C R U D HD | R | R | R |
| Puentes | C R U D HD | C R U D | R | R |
| Tirantes | C R U D HD | C R U D | R | R |
| Estados de tirante (versiones) | C R U D HD | C R U D | R | R |
| Tipos de toron | C R U D HD | C R U D | R | R |
| Sensores/instalaciones | C R U D HD | C R U D | R | R |
| Campanas de adquisicion | C R U D HD | C R U D | R | R |
| Archivos raw/normalizados | C R U D HD | C R U D | R | R |
| Mapeo canal->tirante | C R U D HD | C R U D | R | R |
| Pesajes directos | C R U D HD | C R U D | R | R |
| Snapshots de configuracion | C R U D HD | C R U D | R | R |
| Calibraciones K | C R U D HD | C R U D | R | R |
| Runs de analisis | C R U D HD | C R U D | C R U | R |
| Resultados de analisis | C R U D HD | C R U D | C R U | R |
| Aprobacion de analisis | A R | R | A R | R |
| Historico y resumen | R | R | R | R |
| Exportacion de bitacora | R | R | R | - |

## Reglas adicionales
- Hard delete solo admin y siempre con motivo textual obligatorio.
- Todas las acciones C/U/D/A generan evento de auditoria.
- Viewer no realiza cambios; solo lectura.
- Reviewer puede ejecutar analisis y aprobar, pero no editar catalogo estructural.
- Analyst opera el flujo tecnico diario sin privilegios de gestion de usuarios.
