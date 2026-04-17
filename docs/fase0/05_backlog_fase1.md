# Backlog Tecnico - Fase 1

## Objetivo Fase 1
- Entregar stack Docker reproducible, PostgreSQL como unica fuente de verdad, migraciones formales y base de autenticacion/roles funcionando.

## Entregables obligatorios
- Compose dev/qa/prod consistente con healthchecks.
- Migraciones Alembic iniciales y pipeline de upgrade/downgrade.
- Eliminacion de rutas SQLite en app y scripts operativos.
- Autenticacion JWT con access + refresh token.
- RBAC base alineado a roles: admin, analyst, reviewer, viewer.
- Auditoria base de login y acciones CRUD protegidas.

## Epicas y historias (priorizadas)

### EPIC F1-01 Plataforma Docker y configuracion
- US-01: Como desarrollador quiero levantar entorno completo con un solo comando.
- US-02: Como equipo quiero healthchecks para db/backend/frontend.
- US-03: Como operador quiero variables de entorno claras por entorno (dev/qa/prod).
- Tareas:
- Definir archivos compose por entorno.
- Configurar health endpoints y restart policies.
- Documentar bootstrap y troubleshooting.
- Prioridad: Alta.

### EPIC F1-02 PostgreSQL como unica fuente de verdad
- US-04: Como equipo quiero bloquear uso de SQLite en runtime productivo.
- US-05: Como desarrollador quiero validaciones de arranque que fallen si DATABASE_URL no es PostgreSQL.
- Tareas:
- Refactor de configuracion para requerir esquema postgresql.
- Limpieza de scripts y README para quitar flujos ambiguos.
- Ajuste de tests para no depender de sqlite en pipeline principal.
- Prioridad: Alta.

### EPIC F1-03 Migraciones y esquema versionado
- US-06: Como equipo quiero gestionar cambios de esquema con Alembic.
- US-07: Como operador quiero poder hacer upgrade/downgrade controlado.
- Tareas:
- Inicializar Alembic y baseline del esquema actual.
- Crear migracion inicial alineada con reglas de Fase 0.
- Integrar comando de migracion en flujo de despliegue.
- Prioridad: Alta.

### EPIC F1-04 Auth y JWT base
- US-08: Como usuario quiero login real contra base de datos.
- US-09: Como sistema quiero access token 8h y refresh 7 dias.
- US-10: Como admin quiero gestion basica de usuarios y roles.
- Tareas:
- Implementar endpoints /auth/login, /auth/refresh, /auth/logout.
- Endurecer hashing de password y politica minima.
- Aplicar guardas de autenticacion en endpoints protegidos.
- Prioridad: Alta.

### EPIC F1-05 RBAC base
- US-11: Como plataforma quiero permisos por rol en endpoints criticos.
- US-12: Como reviewer quiero aprobar analisis sin modificar catalogo.
- Tareas:
- Implementar middleware/dependencias de rol por recurso.
- Validar matriz RBAC con pruebas de autorizacion.
- Exponer mensajes de error 401/403 claros.
- Prioridad: Alta.

### EPIC F1-06 Auditoria base
- US-13: Como auditor quiero rastrear quien hizo que y cuando.
- Tareas:
- Registrar eventos de login/logout.
- Registrar CRUD protegido en entidades tecnicas.
- Guardar usuario, accion, entidad, timestamp, ip, motivo cuando aplique.
- Prioridad: Alta.

### EPIC F1-07 Calidad minima de entrega
- US-14: Como equipo quiero pruebas confiables para no romper flujos base.
- Tareas:
- Unit tests de auth y RBAC.
- Integracion API+PostgreSQL para login y CRUD protegido.
- Smoke test de arranque Docker y healthchecks.
- Prioridad: Alta.

## Definicion de terminado Fase 1
- Stack levanta en limpio con Docker en dev y qa.
- Sin dependencia funcional de SQLite.
- Migraciones versionadas aplican en entorno nuevo.
- Login/refresh/RBAC/auditoria base operativos.
- Suite minima de pruebas en verde.
- Documentacion de operacion actualizada.

## Riesgos principales y mitigacion
- Riesgo: deuda tecnica por mezcla ORM/schema.sql.
- Mitigacion: baseline Alembic como fuente unica para evolucion.
- Riesgo: ruptura de tests heredados.
- Mitigacion: separar tests legacy y tests target PostgreSQL.
- Riesgo: ambiguedad de permisos.
- Mitigacion: pruebas parametrizadas por rol desde inicio.

## Estimacion inicial
- Duracion: 2 a 3 semanas calendario.
- Equipo minimo: 1 backend, 1 fullstack, 1 QA/soporte validacion.
