# Proyectos

Spec técnico de la entidad `Project`, tercer nivel de la jerarquía Organización → Grupo → **Proyecto** → Tarea. Modelo y endpoints en un solo spec porque se implementaron juntos en esta tanda.

> Probado end-to-end contra la base Postgres real (crear, listar, ver, editar, eliminar, permisos cruzados) junto con [grupos-abm.md](grupos_y_roles/grupos-abm.md).

## 1. Resumen

- App Django: `app/tasks` (hasta ahora vacía — ver [README.md](../README.md), que ya la reservaba para esto). Registrada como `app.tasks` (label `tasks`).
- Un `Project` pertenece a **un único** `Group` (sección 2.1 del documento: "Un Proyecto pertenece a un único Grupo"), obligatorio desde la creación.
- **Decisión de diseño**: el documento separa RF-20 ("Owner crea proyectos dentro de la organización") de RF-21 ("Owner asigna un proyecto a un único grupo") como dos acciones. Acá se unificaron en una sola operación: el grupo es obligatorio en el `POST` (no existen proyectos "sin grupo" en ningún momento). Se eligió así por simplicidad — un paso en vez de dos, sin estado intermedio "proyecto huérfano" que haya que contemplar en el resto de la API.
- Base URL: `/api/v1/organizations/{organization_id}/groups/{group_id}/projects/` — anidada bajo el grupo dueño, ya que el grupo es parte de la identidad del proyecto (no tiene sentido un proyecto fuera de ese contexto).
- JWT + JSON:API, mismo patrón que el resto de la API. Autorización resuelta a mano en el servicio (ver [common.py](../app/tasks/services/common.py), [project_service.py](../app/tasks/services/project_service.py)) — acá el servicio importa modelos de `app.organizations` directamente (`Organization`, `Group`, `Membership`, `GroupMembership`) para resolver el rol del usuario, porque los permisos de Proyecto dependen enteramente de la organización/grupo dueños, no de nada propio de `app.tasks`.

## 2. Modelo de datos

### `Project`

[app/tasks/models/project.py](../app/tasks/models/project.py)

| Campo | Tipo | Notas |
|---|---|---|
| `group` | FK → `organizations.Group`, `on_delete=CASCADE` | `related_name='projects'`, obligatorio |
| `name` | CharField(255) | |
| `description` | TextField, `blank=True`, default `''` | Opcional |
| `created_at` | DateTimeField, `auto_now_add=True` | |

- Tabla: `projects`.
- No tiene un FK directo a `Organization`: se llega a ella vía `project.group.organization` (evita duplicar la relación — el grupo ya sabe a qué organización pertenece).
- `on_delete=CASCADE`: si se borra el `Group`, se borran sus proyectos (parte de la cascada de RF-16/RF-22).
- Deliberadamente **no tiene campo de estado** (`status`): el propio documento lo deja como pregunta abierta en su sección 9 ("Definir si el estado de un proyecto se cierra automáticamente al completarse todas sus tareas, o si el cierre lo realiza el Owner manualmente") — agregar un campo de estado ahora sería adivinar una decisión que el documento marca explícitamente como pendiente.

## 3. Endpoints

| Método | Path | Quién puede | RF |
|---|---|---|---|
| POST | `/projects` | Owner de la organización | RF-20, RF-21 (unificados, ver §1) |
| GET | `/projects` | Owner/admin de la organización, o miembro del grupo | RF-24 |
| GET | `/projects/{id}` | ídem | — |
| PATCH | `/projects/{id}` | Owner | — |
| DELETE | `/projects/{id}` | Owner | RF-22 |

### 3.1. `POST /projects` — crear proyecto

```json
{ "data": { "type": "projects", "attributes": { "name": "API Core", "description": "Servicios REST del backend" } } }
```

`description` es opcional (default `""`). El `group` sale de la URL, no del body (ya es parte del path `.../groups/{group_id}/projects`).

**Response 201**
```json
{ "data": { "type": "projects", "id": "1", "attributes": { "name": "API Core", "description": "Servicios REST del backend", "group_id": 2 } } }
```

**Errores**: `404` (organización o grupo inexistente — mismo código para "no existe la org" y "no existe el grupo dentro de ella", no se distingue), `403` (no-owner), `400` (falta `name`).

### 3.2. `GET /projects` — listar proyectos del grupo

Visible para Owner/Admin de la organización (supervisión general) o cualquier miembro del grupo — group lead o contributor (RF-24: "mostrar al Group Lead los proyectos asignados a su grupo"; se extendió a Contributor porque sus tareas van a vivir dentro de estos proyectos).

```json
{ "data": [ { "type": "projects", "id": "1", "attributes": { "name": "API Core", "description": "Servicios REST del backend", "group_id": 2 } } ] }
```

### 3.3-3.5. `GET` / `PATCH` / `DELETE /projects/{id}`

Mismo patrón que el resto de la API (ver organizaciones-abm.md §2.3-2.5). El `PATCH` es parcial: acepta `name` y/o `description`. `DELETE` es Owner-only (RF-22: "se eliminan las tareas en cascada" — la cascada hacia `Task` queda preparada a nivel de FK una vez que ese modelo exista; hoy un proyecto no tiene tareas que arrastrar).

## 4. Decisiones de diseño

- **Grupo obligatorio al crear, no un `PATCH` de asignación separado**: ver §1. Si en el futuro hiciera falta mover un proyecto de un grupo a otro, se puede agregar sin romper nada (un `PATCH` que acepte `group_id`), pero no se implementó porque no estaba pedido y el documento no lo menciona como caso de uso.
- **Anidado bajo grupo en la URL, no un recurso plano `/api/v1/projects/`**: coherente con que el grupo es obligatorio y parte de la identidad del proyecto — evita necesitar un query param `?group_id=` para listar.
- **Sin campo de estado**: ver nota en la tabla del modelo.

## 5. Notas sobre el estado actual

- `Task` no existe todavía — es el siguiente nivel de la jerarquía. La cascada de borrado de Proyecto hacia Tareas (RF-22) está preparada a nivel de diseño (mismo patrón `on_delete=CASCADE` que se usó en el resto) pero no hay nada que efectivamente cascadee todavía.
- No hay validación de límites de plan (sección 8.5 del documento: plan Free tope "2 Proyectos activos") antes de crear un proyecto.
- El estado de un proyecto (abierto/cerrado) queda sin definir, como anota el propio documento en su sección 9.
