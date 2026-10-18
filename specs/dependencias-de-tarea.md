# Dependencias entre tareas

Spec técnico de `TaskDependency`, cubre RF-32 a RF-37 (RF-38, notificar al desbloquearse, queda fuera — no hay sistema de notificaciones en el proyecto). Es la segunda de las tres funcionalidades diferenciales del documento (sección 4.1), junto con Workload (implementado) y Modo Foco (no implementado).

> Probado end-to-end contra la base Postgres real: cadena de 3 tareas, ciclo directo, ciclo indirecto, bloqueo FS, bloqueo FF (sin bloquear el arranque), desbloqueo automático al completar la bloqueante, visibilidad por rol, y cascada de borrado.

## 1. Resumen

- Modelo nuevo `TaskDependency` en `app/tasks`, junto a `Task`.
- **Recurso a nivel de proyecto, no anidado bajo una tarea puntual**: una dependencia conecta dos tareas del mismo proyecto, no pertenece más a una que a la otra. El `GET` del listado completo **es** el grafo de RF-37: el frontend lo combina con `GET .../tasks` (que ya existe) para tener nodos (tareas) + aristas (dependencias) y dibujarlo con una librería de grafos (ngx-graph, Cytoscape.js, etc.) — no hace falta un endpoint de "grafo" con forma especial.
- Dos modalidades, igual que el documento (sección 4.1):
  - **FS (Finish to Start)**: la tarea bloqueada no puede *arrancar* (salir de `pending`) hasta que la bloqueante esté `done`.
  - **FF (Finish to Finish)**: la tarea bloqueada no puede *completarse* (`done`) hasta que la bloqueante esté `done` — pero sí puede estar `in_progress` en paralelo.
- El bloqueo de cambio de estado (RF-33) y el desbloqueo automático (RF-35) **no son una acción ni un campo persistido** — se calculan en el momento, tanto al intentar cambiar el `status` de una tarea (rechazo con `409`) como al pedir el detalle de una tarea (campo `blocked` calculado). No hace falta "desbloquear" nada manualmente: en cuanto la bloqueante pasa a `done`, el cálculo cambia solo.

## 2. Modelo de datos

### `TaskDependency`

[app/tasks/models/task_dependency.py](../app/tasks/models/task_dependency.py)

| Campo | Tipo | Notas |
|---|---|---|
| `blocking_task` | FK → `Task`, `on_delete=CASCADE` | `related_name='blocks'` — la tarea que tiene que completarse primero |
| `blocked_task` | FK → `Task`, `on_delete=CASCADE` | `related_name='blocked_by'` — la tarea que depende de la anterior |
| `dependency_type` | CharField, choices `FS` / `FF` | |
| `created_at` | DateTimeField, `auto_now_add=True` | |

- Tabla: `task_dependencies`.
- `UniqueConstraint(blocking_task, blocked_task)`: no puede haber dos filas para el mismo par ordenado (si ya existe A→B, no se puede volver a crear A→B, sea del mismo tipo o de otro).
- `CheckConstraint`: `blocking_task != blocked_task` a nivel de base de datos — una tarea no puede depender de sí misma, reforzado además en el servicio antes de pegarle a la DB (mensaje de error más claro que el que tiraría el constraint).
- `on_delete=CASCADE` en ambas FKs: si se borra cualquiera de las dos tareas, la dependencia se borra con ella (probado explícitamente).

## 3. Endpoints

| Método | Path | Quién puede | RF |
|---|---|---|---|
| POST | `/projects/{id}/dependencies` | Group lead del grupo dueño del proyecto | RF-32, RF-34 |
| GET | `/projects/{id}/dependencies` | Owner/admin/group lead ven todas; contributor solo las que involucran alguna tarea asignada a él | RF-37 |
| DELETE | `/projects/{id}/dependencies/{dependency_id}` | Group lead | RF-36 |

### 3.1. `POST /dependencies` — crear dependencia (RF-32)

```json
{ "data": { "type": "task_dependencies", "attributes": { "blocking_task_id": 10, "blocked_task_id": 14, "dependency_type": "FS" } } }
```

**Validaciones, en orden** (ver [dependency_service.py](../app/tasks/services/dependency_service.py)):
1. Ambos ids tienen que ser tareas que existen **en este proyecto** (`400`/`404` si no).
2. No puede ser auto-dependencia (`400`).
3. No puede repetirse el mismo par (`409`).
4. **Detección de ciclos (RF-34)**: no puede generar un ciclo circular, directo (A→B y B→A) ni indirecto a través de una cadena (A→B→C, y después C→A) — `400`.

**Response 201**
```json
{
  "data": {
    "type": "task_dependencies",
    "id": "5",
    "attributes": {
      "blocking_task_id": 10,
      "blocking_task_title": "Diseñar schema",
      "blocked_task_id": 14,
      "blocked_task_title": "Implementar endpoint",
      "dependency_type": "FS"
    }
  }
}
```

#### Cómo funciona la detección de ciclos

Agregar una arista `blocking_task → blocked_task` cierra un ciclo si **`blocking_task` ya es alcanzable desde `blocked_task`** siguiendo las dependencias que ya existen (porque entonces se formaría `blocking_task → blocked_task → ... → blocking_task`). `_creates_cycle()` hace un recorrido (DFS iterativo, con pila) desde `blocked_task_id` siguiendo los `blocked_task` de cada dependencia existente, y devuelve `True` si en algún momento llega a `blocking_task_id`. Cubre tanto el ciclo directo (A→B, se intenta B→A) como el indirecto (A→B→C, se intenta C→A) — ambos casos están probados.

### 3.2. `GET /dependencies` — listar (RF-37, el grafo)

Owner/Admin/Group lead ven **todas** las dependencias del proyecto. Un contributor ve únicamente las dependencias donde al menos una de las dos tareas (`blocking_task` o `blocked_task`) le está asignada — mismo criterio de "no mostrarle cosas que no le corresponden" que el resto de la API (RF-31).

### 3.3. `DELETE /dependencies/{id}` — eliminar (RF-36)

Solo group lead. **Errores**: `404` (dependencia inexistente en este proyecto), `403` (no es group lead).

## 4. Bloqueo de cambio de estado (RF-33) y desbloqueo automático (RF-35)

No son endpoints propios: se enganchan en `actualizar_tarea` (tanto la rama de group lead como la de contributor), en [task_service.py](../app/tasks/services/task_service.py), **antes** de guardar un `status` nuevo:

```python
def _dependency_block_reason(task, new_status):
    ...
```

- Mira las dependencias donde esta tarea es `blocked_task` y cuya bloqueante **todavía no está `done`**.
- Si alguna es `FS` y el `new_status` pedido no es `pending` → bloquea.
- Si alguna es `FF` y el `new_status` pedido es `done` → bloquea.
- Si hay bloqueo, el `PATCH` devuelve **`409 Conflict`** (no `400`: el request está bien formado, es un conflicto de estado) con el detalle de qué tarea falta completar y de qué tipo es la dependencia.

El "desbloqueo automático" (RF-35) es, en los hechos, que esta misma función deja de encontrar motivos de bloqueo en cuanto la bloqueante pasa a `done` — no hay ninguna acción ni job que "desbloquee" nada.

### 4.1. Indicador visual (`blocked`) en el recurso de tarea

`GET`/`POST`/`PATCH` de `Task` ahora devuelven un campo `blocked` (booleano) en `attributes`, pensado para el "ícono de candado" que pide la sección 4.1 del documento ("La tarea bloqueada muestra un ícono de candado"). Se calcula solo a partir de dependencias **FS** pendientes — una FF no impide arrancar la tarea (puede estar `in_progress`), solo completarla, así que no cuenta para este indicador. Ver [tareas.md](tareas.md) para el resto del recurso `Task`.

## 5. Decisiones de diseño

- **Sin endpoint de "grafo" dedicado**: ver §1 — `GET /dependencies` + `GET /tasks` ya dan toda la data que necesita el frontend. Evita duplicar formato de datos para el mismo contenido.
- **`409`, no `400`, para el bloqueo de cambio de estado**: el body del request es válido (`status` es un valor correcto), lo que falla es una precondición de negocio sobre el estado actual del sistema — semánticamente es un conflicto, no una mala request.
- **`blocked` se calcula, no se persiste**: evita que quede desincronizado si se borra una dependencia o se completa la bloqueante por otra vía — siempre reflejafiel el estado real en el momento de la consulta.

## 6. Notas sobre el estado actual

- **RF-38 (notificar al responsable cuando se desbloquea)** no implementado — no hay ningún sistema de notificaciones en el proyecto todavía.
- **Costo de `blocked`**: agrega una query por cada tarea serializada (potencial N+1 en `listar_tareas` con muchas tareas). No se optimizó porque la escala actual del proyecto no lo justifica; si se vuelve un problema real, se puede precalcular con un `annotate`/`prefetch_related` sin cambiar el contrato de la API.
- `_dependency_block_reason` recorre **todas** las dependencias donde la tarea es `blocked_task`, no solo la primera — si hay varias bloqueantes incompletas, informa la primera que encuentra (no junta todos los motivos en un solo mensaje). Alcanza para el caso de uso actual; si hiciera falta listar todos los bloqueos a la vez, es un cambio chico.
