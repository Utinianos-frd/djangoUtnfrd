# Tareas (ABM + asignación)

Spec técnico de la entidad `Task`, último nivel de la jerarquía Organización → Grupo → Proyecto → **Tarea**. Cubre RF-25 a RF-29 y RF-31 (ABM, asignación múltiple, cambio de estado, visibilidad por rol). Comentarios (RF-30) y dependencias FS/FF (RF-32 a RF-37) están implementados en specs aparte: ver [comentarios-de-tarea.md](comentarios-de-tarea.md) y [dependencias-de-tarea.md](dependencias-de-tarea.md).

> Probado end-to-end contra la base Postgres real, incluyendo la cascada Proyecto → Tarea.

## 1. Resumen

- Modelo y endpoints en `app/tasks`, junto a `Project`.
- Una `Task` pertenece a un único `Project` (obligatorio).
- **Asignación múltiple**: una tarea puede tener **varios** responsables (`ManyToManyField` a `Users`), tal como pide RF-26 ("asignar cada tarea a uno o más miembros de su grupo") — a diferencia de `Membership`/`GroupMembership`, acá no hace falta un modelo intermedio propio porque no hay ningún atributo extra por asignación (ni rol, ni fecha); el `ManyToManyField` de Django alcanza.
- Base URL: `/api/v1/organizations/{organization_id}/groups/{group_id}/projects/{project_id}/tasks/...` — mismo criterio de anidamiento que Proyecto bajo Grupo.
- Autorización resuelta en el servicio, igual que el resto de la API — ver [task_service.py](../app/tasks/services/task_service.py).

## 2. Modelo de datos

### `Task`

[app/tasks/models/task.py](../app/tasks/models/task.py)

| Campo | Tipo | Notas |
|---|---|---|
| `project` | FK → `tasks.Project`, `on_delete=CASCADE` | `related_name='tasks'`, obligatorio |
| `title` | CharField(255) | |
| `status` | CharField, choices `pending` / `in_progress` / `done` | `default='pending'` |
| `assignees` | ManyToManyField → `Users` | `related_name='assigned_tasks'`, `blank=True` (una tarea puede no tener a nadie asignado todavía) |
| `created_at` | DateTimeField, `auto_now_add=True` | |

- Tabla: `tasks`.
- `on_delete=CASCADE` en `project`: si se borra el proyecto, se borran sus tareas (parte de RF-22/RF-28).
- **`status` con tres valores fijos** (`pending`/`in_progress`/`done`), no definidos explícitamente por el documento pero necesarios para que RF-29 ("cambiar el estado") tenga sentido. `done` es el estado que usan las dependencias como "completada" (RF-33, RF-35 — ver [dependencias-de-tarea.md](dependencias-de-tarea.md)). No hay un valor `blocked` en `status`: el bloqueo es una propiedad derivada, calculada en el momento (campo `blocked` en el recurso), no un estado persistido.
- Sin campo `description`: mismo criterio que `Project` (ver [proyectos.md §2](proyectos.md)) — el documento no lo pide y se mantiene el modelo mínimo.

## 3. Endpoints

| Método | Path | Quién puede | RF |
|---|---|---|---|
| POST | `/tasks` | Group lead del grupo dueño del proyecto | RF-25, RF-26 |
| GET | `/tasks` | Group lead/owner/admin ven todas; contributor ve solo las asignadas a él | RF-31 |
| GET | `/tasks/{id}` | ídem, a nivel de una tarea puntual | RF-31 |
| PATCH | `/tasks/{id}` | Group lead: todo. Contributor asignado: solo `status` | RF-27, RF-29 |
| DELETE | `/tasks/{id}` | Group lead | RF-28 |

**Lectura literal de la matriz** (igual criterio que en grupos-abm.md): la tabla de permisos a nivel tarea (sección 3.2) solo tiene columnas Group Lead/Contributor para crear, asignar, editar y eliminar tareas — ni Owner ni Admin aparecen. Por eso **crear, eliminar y editar estructuralmente** una tarea (título, asignados) es exclusivo del group lead. Owner/Admin sí pueden **ver** todas las tareas (oversight), extendiendo el mismo criterio que ya se usó para Grupo y Proyecto — el documento no lo prohíbe y es consistente con que Owner/Admin ya ven todo lo demás de la organización.

### 3.1. `POST /tasks` — crear tarea

```json
{ "data": { "type": "tasks", "attributes": { "title": "Implementar login", "description": "Login con JWT", "assignee_ids": [5, 8] } } }
```

`description` (texto libre) es opcional, default `""`. `assignee_ids` es opcional (default `[]` — una tarea puede crearse sin asignar a nadie todavía). Cada id debe corresponder a un usuario con una `GroupMembership` en el grupo dueño del proyecto (cualquier rol, group lead o contributor) — si alguno no lo es, `400` con el detalle de qué ids fallaron.

**Response 201**
```json
{ "data": { "type": "tasks", "id": "1", "attributes": { "title": "Implementar login", "description": "Login con JWT", "closed_at": null, "status": "pending", "project_id": 3, "assignee_ids": [5, 8], "blocked": false } } }
```

Si alguno de los asignados queda sobrecargado con esta asignación, la response trae además un bloque `meta.warnings` (no bloquea la creación) — ver [workload.md §4](workload.md).

**Errores**: `404` (organización, grupo o proyecto inexistente), `403` (no es group lead), `400` (falta `title`, o algún `assignee_id` no es miembro del grupo).

### 3.2. `GET /tasks` — listar tareas del proyecto (RF-31)

- Group lead, owner u admin: ven **todas** las tareas del proyecto.
- Contributor: ve **únicamente** las tareas donde aparece en `assignees` (`Task.objects.filter(project=project, assignees=request.user)`). Si no es miembro del grupo en absoluto, `403`.

### 3.3. `GET /tasks/{id}` — ver una tarea

Mismo criterio de visibilidad que el listado, pero a nivel de una tarea puntual: un contributor que pide el detalle de una tarea que no tiene asignada recibe `403`, no el contenido. Probado explícitamente (incluyendo el caso de que deja de verla si el group lead la reasigna a otra persona).

### 3.4. `PATCH /tasks/{id}` — editar tarea

Dos caminos según el rol de quien hace el request (RF-27 vs. RF-29):

- **Group lead**: puede cambiar `title`, `description`, `status` y/o `assignee_ids` (valida los nuevos `assignee_ids` igual que en el create). Es un `PATCH` parcial — solo toca los campos presentes en el body. Si el body trae `assignee_ids`, la response puede incluir `meta.warnings` igual que en el create (ver [workload.md §4](workload.md)).
- **Contributor asignado a la tarea**: **solo** puede enviar `status`. Si el body trae cualquier otro campo (`title`, `description`, `assignee_ids`), `400` — no se ignora silenciosamente, se rechaza explícitamente para que quede claro que no tiene permiso sobre esos campos. Si no está asignado a la tarea, `403` (ni siquiera puede cambiar el status de una tarea ajena).

**Fecha de cierre (`closed_at`)**: la maneja el backend, no se puede enviar. Cuando una tarea pasa a `done` (la mueva el group lead o el contributor) se guarda el momento; si vuelve a `pending`/`in_progress` queda en `null`. Reenviar `done` a una tarea ya completada no cambia la fecha.

**Errores**: `404` (tarea/proyecto/grupo/organización inexistente), `403` (contributor no asignado, o usuario sin rol en el grupo), `400` (validación de serializer, `assignee_ids` inválidos, o contributor mandando campos no permitidos).

### 3.5. `DELETE /tasks/{id}` — eliminar tarea

Solo group lead (RF-28). RF-28 también menciona "se eliminan las dependencias a otras tareas": cubierto por `on_delete=CASCADE` en `TaskDependency` — ver [dependencias-de-tarea.md](dependencias-de-tarea.md).

## 4. Decisiones de diseño

- **`assignee_ids` como lista de ints, no de objetos**: coherente con mantener el payload simple; el recurso devuelto expone `assignee_ids` (no objetos de usuario completos) para no acoplar este endpoint a los datos de `app.users` — si el frontend necesita nombre/email de cada asignado, los resuelve contra `GET /organizations/{id}/members` o `/groups/{id}/members`, que sí devuelven `username`.
- **Contributor no puede tocar título ni asignados de "sus propias" tareas**: la matriz dice "Editar sus propias tareas: Contributor sí", pero interpretado junto con RF-29 ("cambiar el **estado** de sus tareas asignadas") se tomó como que esa fila de la matriz se refiere específicamente a avanzar el estado de la tarea, no a editarla estructuralmente — eso quedaría raro (un contributor renombrando su propia tarea o sacándose a otro asignado). Si esta lectura no es la que quieren, es un cambio chico (ampliar qué campos acepta `UpdateTaskStatusSerializer` para contributors).
- **Owner/Admin pueden ver pero no crear/editar/eliminar tareas**: ver "lectura literal de la matriz" en la sección 3.

## 5. Notas sobre el estado actual (explícitamente fuera de esta tanda)

- **Dependencias entre tareas** (RF-32 a RF-37) ya están implementadas — ver [dependencias-de-tarea.md](dependencias-de-tarea.md). RF-38 (notificar al desbloquear) sigue pendiente: no hay sistema de notificaciones.
- **Comentarios** (RF-30) ya están implementados — ver [comentarios-de-tarea.md](comentarios-de-tarea.md).
- **Notificaciones** (RF-38, notificar al desbloquearse una tarea) no están en el alcance de este proyecto todavía — no hay ningún sistema de notificaciones en el código.
