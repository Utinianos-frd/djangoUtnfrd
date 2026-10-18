# Modo Foco

Spec técnico de `FocusSession` y `Pomodoro`, cubre RF-46 a RF-53. Es la tercera y última funcionalidad diferencial del documento (sección 4.3), junto con Workload y Dependencias entre tareas (ambas implementadas). RF-54/RF-55 (notificaciones durante la sesión) quedan fuera — no hay sistema de notificaciones en el proyecto.

> Probado end-to-end contra la base Postgres real: bloqueo por plan Free, habilitación en plan Pro, una sola sesión activa por usuario, un solo pomodoro activo por sesión, ciclo completo pausar→reanudar→completar, sugerencia de descanso (5 min normal, 15 min cada 4 consecutivos, confirmado explícitamente), completar una tarea sin salir del modo foco, y el resumen final.

## 1. Resumen

- App nueva `app/focus` (`FocusSession`, `Pomodoro`), separada de `app/tasks` — es su propio dominio (sesiones de productividad personal), aunque referencia `Task` por FK/M2M con `'tasks.Task'` (string, sin import directo — evita acoplar `app.tasks` a `app.focus` en la dirección inversa).
- **Recurso a nivel de usuario, no anidado bajo organización/grupo/proyecto**: a diferencia de todo lo demás construido hasta ahora, una sesión de foco es personal — las tareas que elegís pueden (en teoría) pertenecer a proyectos o incluso organizaciones distintas, así que no tiene sentido anidarla bajo una sola. Mismo criterio que `GET /api/v1/auth/me`. Base URL: `/api/v1/focus-sessions/`.
- **Exclusivo del plan Pro** (sección 8.3/8.4 del documento) — es el primer chequeo de plan real implementado en todo el proyecto. Si la organización dueña de alguna tarea elegida está en plan Free, el inicio de sesión se rechaza con `403`.
- El timing de los 25 minutos del pomodoro **lo controla el cliente** — el backend no corre ningún temporizador ni job en segundo plano; solo valida que las transiciones de estado (correr → pausar → reanudar → completar/cancelar) sean legales y registra los timestamps.

## 2. Modelo de datos

### `FocusSession`

[app/focus/models/focus_session.py](../app/focus/models/focus_session.py)

| Campo | Tipo | Notas |
|---|---|---|
| `user` | FK → `Users`, `on_delete=CASCADE` | `related_name='focus_sessions'` |
| `goal_text` | TextField | RF-47: qué quiere lograr en la sesión |
| `status` | CharField, choices `active` / `ended` | `default='active'` |
| `tasks` | ManyToManyField → `tasks.Task` | Las tareas elegidas como objetivo (RF-47), `blank=True` a nivel de esquema pero el serializer exige al menos una |
| `started_at` | DateTimeField, `auto_now_add=True` | |
| `ended_at` | DateTimeField, nullable | Se completa al terminar la sesión |

- `UniqueConstraint(user, condition=Q(status='active'))`: **una sola sesión activa por usuario a la vez** — mismo patrón de índice único parcial que ya usamos para "un solo owner" y "un solo group lead".

### `Pomodoro`

[app/focus/models/pomodoro.py](../app/focus/models/pomodoro.py)

| Campo | Tipo | Notas |
|---|---|---|
| `session` | FK → `FocusSession`, `on_delete=CASCADE` | `related_name='pomodoros'` |
| `task` | FK → `tasks.Task`, `on_delete=CASCADE` | `related_name='pomodoros'` — RF-51, el "historial de la tarea" es justamente esta FK (consultable como `task.pomodoros.filter(status='completed')`, ver §6) |
| `status` | CharField, choices `running`/`paused`/`completed`/`cancelled` | `default='running'` |
| `started_at` | DateTimeField, `auto_now_add=True` | |
| `paused_at` | DateTimeField, nullable | Seteado mientras está pausado; se limpia al reanudar |
| `total_paused_seconds` | PositiveIntegerField | Acumula el tiempo pausado a través de ciclos pausar/reanudar |
| `completed_at` | DateTimeField, nullable | |

`DURATION_MINUTES = 25` es una constante de clase (Python), no un campo — el documento fija el pomodoro en 25 minutos siempre (RF-49), no hay necesidad de que sea configurable.

## 3. Endpoints

| Método | Path | RF |
|---|---|---|
| POST | `/focus-sessions/` | RF-46, RF-47 (iniciar sesión) |
| GET | `/focus-sessions/active` | — (consultar mi sesión activa) |
| POST | `/focus-sessions/{id}/end` | RF-53 (terminar + resumen) |
| POST | `/focus-sessions/{id}/pomodoros` | RF-49 (iniciar pomodoro) |
| PATCH | `/focus-sessions/{id}/pomodoros/{pomodoro_id}` | RF-49, RF-50, RF-51 (pausar/reanudar/cancelar/completar) |

Todos requieren autenticación; no hay chequeo de rol de organización — la única regla de pertenencia es "la sesión/pomodoro es tuyo" (`session.user == request.user`).

### 3.1. `POST /focus-sessions/` — iniciar sesión (RF-46, RF-47)

```json
{ "data": { "type": "focus_sessions", "attributes": { "goal_text": "Terminar el endpoint de login", "task_ids": [14, 18] } } }
```

Validaciones, en orden:
1. `task_ids` no puede estar vacío (RF-47: elegís tareas *antes* de empezar).
2. Todos los ids tienen que existir (`400` si no).
3. Cada tarea tiene que estar asignada al usuario que inicia la sesión (`403` si no — no podés "enfocarte" en una tarea que no es tuya).
4. **La organización dueña de cada tarea tiene que estar en plan Pro** (`403` con el nombre de la organización si no lo está).
5. No puede haber ya una sesión `active` para este usuario (`409`).

**Response 201**
```json
{
  "data": {
    "type": "focus_sessions",
    "id": "3",
    "attributes": {
      "goal_text": "Terminar el endpoint de login",
      "status": "active",
      "task_ids": [14, 18],
      "started_at": "2026-10-18T15:00:00.123456Z",
      "ended_at": null
    }
  }
}
```

### 3.2. `GET /focus-sessions/active`

Para que el frontend sepa si hay una sesión en curso (por ejemplo, al recargar la página). `404` si no hay ninguna.

### 3.3. `POST /focus-sessions/{id}/pomodoros` — iniciar pomodoro (RF-49)

```json
{ "data": { "type": "pomodoros", "attributes": { "task_id": 14 } } }
```

`task_id` tiene que ser una de las tareas elegidas al iniciar la sesión (`400` si no). Solo puede haber un pomodoro `running`/`paused` por sesión a la vez (`409` si ya hay uno). **Errores**: `404` (sesión ajena o inexistente), `409` (sesión ya terminada, o ya hay un pomodoro en curso).

### 3.4. `PATCH /focus-sessions/{id}/pomodoros/{pomodoro_id}` — pausar / reanudar / cancelar / completar

```json
{ "data": { "type": "pomodoros", "attributes": { "action": "pause" } } }
```

`action` es uno de `pause` / `resume` / `cancel` / `complete`. Máquina de estados:

| Acción | Desde | Hacia | Rechaza si... |
|---|---|---|---|
| `pause` | `running` | `paused` | no está `running` |
| `resume` | `paused` | `running` | no está `paused`; suma el tiempo pausado a `total_paused_seconds` |
| `cancel` | `running`/`paused` | `cancelled` | ya está `completed`/`cancelled` |
| `complete` | `running` | `completed` | no está `running` (si está pausado, hay que reanudarlo primero — decisión deliberada, ver §5) |

Al completar (RF-50), la response trae `meta.suggested_break_minutes` (15 si este es el 4º pomodoro consecutivo completado en la sesión, 8º, 12º..., 5 en cualquier otro caso) y `meta.consecutive_completed`:

```json
{
  "data": { "type": "pomodoros", "id": "9", "attributes": { "status": "completed", "...": "..." } },
  "meta": { "suggested_break_minutes": 15, "consecutive_completed": 4 }
}
```

"Consecutivos" se corta en el primer pomodoro de la sesión que no esté `completed` (mirando del más reciente hacia atrás) — si cancelaste uno en el medio, el contador vuelve a 0 a partir de ahí.

### 3.5. `POST /focus-sessions/{id}/end` — terminar sesión (RF-53)

Cualquier pomodoro que haya quedado `running`/`paused` se cancela automáticamente. Calcula y devuelve el resumen:

```json
{
  "data": {
    "type": "focus_session_summary",
    "id": "3",
    "attributes": {
      "worked_seconds": 1500,
      "pomodoros_completed": 2,
      "tasks_completed_count": 1,
      "tasks_completed_titles": ["Implementar login"]
    }
  }
}
```

- `worked_seconds`: suma, sobre los pomodoros `completed`, de `(completed_at - started_at) - total_paused_seconds`.
- `tasks_completed_*`: tareas de `session.tasks` cuyo `status` sea `done` **al momento de pedir el resumen** (no se trackea cuándo exactamente se completaron respecto a la sesión — ver §6).

## 4. Completar tareas sin salir del modo foco (RF-52)

No es un endpoint nuevo: el frontend sigue usando `PATCH /organizations/.../tasks/{id}` que ya existe (ver [tareas.md](tareas.md)) — un contributor ya puede cambiar el `status` de sus propias tareas. "Sin salir del modo foco" es una decisión de UI (no navegar fuera de la pantalla de sesión), no algo que el backend deba resolver con una ruta distinta.

## 5. Decisiones de diseño

- **Gateado por plan Pro, de verdad**: a diferencia del resto de los límites de plan (que siguen pendientes, ver [organizaciones-abm.md](organizaciones-abm.md) §4), acá sí se implementó porque el documento lo pide explícitamente y de forma puntual (sección 8.4/8.5). Para probarlo hace falta pasar una organización a `plan: "pro"` vía `PATCH /organizations/{id}` (ver [workload.md](workload.md) para el resto de los campos editables de `Organization`).
- **El backend no mide los 25 minutos**: no hay cron, no hay Celery, no hay nada corriendo en segundo plano. El cliente corre su propio timer y llama a `complete` cuando termina — el backend confía en el cliente para el timing, igual criterio que con `logo_url` (no se valida contenido que requeriría infraestructura extra para algo que no es crítico de integridad de datos).
- **`complete` solo desde `running`, no desde `paused`**: fuerza a resumir antes de completar, así el cálculo de `total_paused_seconds` siempre es consistente (no hay ambigüedad de "cuánto duró la pausa final").
- **Una sola sesión activa, un solo pomodoro activo por sesión**: ambos son índices/constraints a nivel de aplicación (el segundo) y de DB (el primero, `UniqueConstraint` condicional) — coherente con que RF-48 habla de "el modo foco" en singular, una experiencia de concentración a la vez, no varias en paralelo.
- **`tasks_completed` es un snapshot al momento de pedir el resumen, no un tracking histórico**: si una tarea ya estaba `done` antes de que arrancara la sesión (caso raro, pero posible si la eligieron igual como parte del objetivo), cuenta igual en el resumen. Simplificación deliberada — trackear "se completó durante la sesión" exactamente requeriría guardar un timestamp de cuándo cada tarea pasó a `done`, que hoy `Task` no tiene.

## 6. Notas sobre el estado actual

- **RF-54/RF-55** (acumular notificaciones durante la sesión, mostrar urgentes sin interrumpir) no implementadas — no hay ningún sistema de notificaciones en el proyecto.
- **RF-51 ("historial de la tarea")**: estructuralmente resuelto (cada `Pomodoro` tiene su `task` FK), pero no hay un endpoint dedicado tipo `GET /tasks/{id}/pomodoros` para consultarlo desde la UI de una tarea — se puede agregar después sin tocar el modelo. No se agregó ahora para no acoplar `app.tasks` con `app.focus` en la dirección contraria a como está hoy (`app.focus` depende de `app.tasks`, no al revés).
- No hay validación de límites de uso de Modo Foco más allá del gate de plan (ej. cuántas sesiones por día) — el documento no lo pide.
