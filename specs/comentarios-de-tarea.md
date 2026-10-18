# Comentarios de tarea

Spec técnico de `Comment`, cubre RF-30 ("El sistema debe permitir al Contributor comentar en cualquier tarea del proyecto que le fue asignada") y la fila "Comentar tarea" de la matriz de permisos (sección 3.2: Group Lead sí, Contributor sí). Complementa [tareas.md](tareas.md).

> Probado end-to-end contra la base Postgres real, incluida la cascada Tarea → Comentario.

## 1. Resumen

- Modelo nuevo en `app/tasks`, junto a `Task`.
- Un comentario pertenece a una única `Task` y tiene un único autor (`Users`).
- Base URL: `/api/v1/organizations/{organization_id}/groups/{group_id}/projects/{project_id}/tasks/{task_id}/comments` — mismo criterio de anidamiento que el resto de la jerarquía.
- Reutiliza los helpers de permisos de [task_service.py](../app/tasks/services/task_service.py) (`_get_org_group_project`, `_can_view_task`, `_is_group_lead`) en vez de duplicar lógica — ver [comment_service.py](../app/tasks/services/comment_service.py).

## 2. Modelo de datos

### `Comment`

[app/tasks/models/comment.py](../app/tasks/models/comment.py)

| Campo | Tipo | Notas |
|---|---|---|
| `task` | FK → `tasks.Task`, `on_delete=CASCADE` | `related_name='comments'` |
| `author` | FK → `Users`, `on_delete=CASCADE` | `related_name='task_comments'` |
| `text` | TextField | Sin límite de longitud |
| `created_at` | DateTimeField, `auto_now_add=True` | |

- Tabla: `task_comments`.
- `Meta.ordering = ['created_at']`: los comentarios siempre se devuelven en orden cronológico, sin tener que pedirlo explícitamente en cada query.
- `on_delete=CASCADE` en `task`: si se borra la tarea, se borran sus comentarios (coherente con el resto de la cascada Organización → ... → Tarea).

## 3. Endpoints

| Método | Path | Quién puede |
|---|---|---|
| GET | `/tasks/{id}/comments` | Owner/admin (oversight), group lead, o contributor asignado a la tarea — mismo criterio que `GET /tasks/{id}` (ver [tareas.md §3.3](tareas.md)) |
| POST | `/tasks/{id}/comments` | Group lead del grupo, o contributor **asignado a esa tarea** |

**Owner/Admin pueden ver pero no comentar**: la matriz solo lista Group Lead/Contributor en la fila "Comentar tarea" — mismo criterio de "oversight es ver, no actuar" que ya se aplicó a crear/editar/eliminar tareas (ver [tareas.md §3](tareas.md), "lectura literal de la matriz"). Está probado explícitamente: el Owner puede listar los comentarios pero recibe `403` si intenta crear uno.

### 3.1. `GET /tasks/{id}/comments` — listar comentarios

```json
{
  "data": [
    {
      "type": "comments",
      "id": "1",
      "attributes": {
        "text": "Arranco con esto",
        "author_id": 5,
        "author_username": "ana",
        "created_at": "2026-10-18T14:30:00.123456Z"
      }
    }
  ]
}
```

**Errores**: `404` (tarea/proyecto/grupo/organización inexistente), `403` (sin acceso a la tarea — mismo criterio de visibilidad que verla).

### 3.2. `POST /tasks/{id}/comments` — comentar

```json
{ "data": { "type": "comments", "attributes": { "text": "Avisame cuando termines" } } }
```

El `author` sale de `request.user`, no del body. **Errores**: `404` (tarea inexistente), `403` (ni group lead ni contributor asignado a esta tarea puntual — ver RF-30: un contributor solo puede comentar tareas que le fueron asignadas, no cualquier tarea del proyecto), `400` (falta `text`).

## 4. Decisiones de diseño

- **Group lead puede comentar cualquier tarea de su grupo, esté o no asignado**: coherente con que ya puede verlas y editarlas todas.
- **Contributor solo comenta tareas asignadas a él**: RF-30 lo dice entre paréntesis ("que le fue asignada") y es consistente con RF-31 (solo ve las suyas) — no tendría sentido poder comentar algo que ni siquiera puede ver en el listado.
- **Sin editar ni eliminar comentarios**: no hay `PATCH`/`DELETE` — el documento no lo pide (RF-30 solo habla de "comentar") y no se agregó por YAGNI. Si hiciera falta después, es un endpoint chico (típicamente: el propio autor puede borrar su comentario).
- **`author_username` va embebido en la respuesta** (no solo `author_id`): evita que el frontend tenga que resolver cada autor contra otro endpoint solo para mostrar quién escribió qué, igual criterio que se usó en los recursos de membership.

## 5. Notas sobre el estado actual

- No hay notificación cuando alguien comenta (ningún sistema de notificaciones existe todavía en el proyecto).
- No hay edición ni borrado de comentarios (ver §4).
- No hay menciones (@usuario) ni formato enriquecido — `text` es texto plano.
