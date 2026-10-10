# Workload (carga de trabajo)

Spec técnico del panel de Workload, una de las tres funcionalidades diferenciales del documento (sección 4.2), junto con dependencias entre tareas (no implementado) y modo foco (no implementado). Cubre RF-39 a RF-45.

> Probado end-to-end contra la base Postgres real: panel, detalle por miembro, umbral configurable, y la advertencia no bloqueante al asignar una tarea a alguien sobrecargado.

## 1. Resumen

- No es una entidad nueva con tabla propia: es una **vista calculada** sobre datos que ya existen (`Task.assignees`, `GroupMembership`), más un único campo de configuración nuevo (`Organization.overload_threshold`).
- **Carga global** (RF-40): la carga de un miembro se calcula sumando sus tareas activas en **todos** los grupos donde participa, no solo en el grupo que se está consultando — porque un `Task.assignees` es una relación directa a `Users` (no pasa por `Group`), contar las tareas activas de un usuario ya da el número global sin necesidad de lógica especial.
- **Tarea activa** = `status` en `pending` o `in_progress` (no `done`). Constante `ACTIVE_STATUSES` en [workload_service.py](../app/organizations/services/workload_service.py).
- **Clasificación de 3 niveles con un solo umbral** (RF-41, RF-44 — el documento habla de "el umbral de sobrecarga" en singular):
  - `available`: 0 tareas activas.
  - `overloaded`: `active_task_count >= overload_threshold`.
  - `busy`: cualquier otro caso (entre 1 y `overload_threshold - 1`).
- Vive en `app/organizations` (no en `app/tasks`), porque el panel es fundamentalmente una vista sobre los miembros de un grupo — aunque el servicio importa `Task` de `app.tasks.models` para contar. No genera import circular: es `organizations.services → tasks.models`, en la misma dirección que ya usa `tasks.services → organizations.models`.

## 2. Modelo de datos

Un solo campo nuevo, agregado a `Organization` (no una tabla nueva):

| Campo | Tipo | Notas |
|---|---|---|
| `overload_threshold` | PositiveIntegerField | `default=5`. Configurable por el Owner (RF-44). |

[app/organizations/models/organization.py](../app/organizations/models/organization.py), migración `0003_organization_overload_threshold`.

## 3. Endpoints

| Método | Path | Quién puede | RF |
|---|---|---|---|
| GET | `/organizations/{org_id}/groups/{group_id}/workload` | Owner, Admin, o el group lead de ese grupo | RF-39, RF-40, RF-41 |
| GET | `/organizations/{org_id}/groups/{group_id}/workload/{user_id}` | ídem | RF-45 |
| PATCH | `/organizations/{org_id}` | Owner (reutiliza el endpoint existente, ver §4) | RF-44 |

El documento dice literal que el panel es "visible para el Group Lead (y, con fines de supervisión, para el Admin)" — no menciona al Owner explícitamente, pero se extendió el acceso a Owner por el mismo criterio de oversight que ya se usó en organizaciones-abm.md, grupos-abm.md y tareas.md: el Owner ve todo lo demás de la organización, no tendría sentido que no pueda ver esto.

### 3.1. `GET /workload` — panel del grupo

```json
{
  "data": [
    {
      "type": "workload",
      "id": "5",
      "attributes": {
        "user_id": 5,
        "username": "ana",
        "group_role": "contributor",
        "active_task_count": 2,
        "status": "overloaded"
      }
    }
  ]
}
```

Una fila por cada `GroupMembership` del grupo (incluye al group lead también, no solo contributors). **Errores**: `404` (grupo inexistente), `403` (quien pide no es owner/admin/group lead de ese grupo).

### 3.2. `GET /workload/{user_id}` — detalle de un miembro (RF-45)

```json
{
  "data": {
    "type": "workload",
    "id": "5",
    "attributes": {
      "user_id": 5,
      "username": "ana",
      "active_task_count": 2,
      "status": "overloaded",
      "active_tasks": [
        { "task_id": 10, "title": "Implementar login", "status": "in_progress", "project_id": 3, "group_id": 1 },
        { "task_id": 14, "title": "Fix bug X", "status": "pending", "project_id": 7, "group_id": 2 }
      ]
    }
  }
}
```

`active_tasks` puede incluir tareas de **otros grupos** (coherente con que la carga es global, §1) — por eso cada item trae su propio `project_id`/`group_id`, no asume el del grupo consultado. **Errores**: `404` (grupo inexistente, o el `user_id` no pertenece a este grupo), `403` (sin permiso).

### 3.3. Configurar el umbral — `PATCH /organizations/{id}` (RF-44)

No es un endpoint nuevo: se agregó `overload_threshold` como campo opcional a `UpdateOrganizationSerializer`, el mismo que ya se usaba para renombrar la organización (ver [organizaciones-abm.md §2.4](organizaciones-abm.md)). Mismo control de acceso (solo Owner).

```json
{ "data": { "type": "organizations", "attributes": { "overload_threshold": 8 } } }
```

`overload_threshold` también se agregó a los `attributes` de toda respuesta que devuelve una organización (crear, listar, ver, etc.).

## 4. Advertencia al asignar (RF-42, RF-43) — enganchada en los endpoints de Tarea existentes

RF-42/43 piden **advertir** (no bloquear) al Group Lead cuando asigna una tarea a alguien sobrecargado, y **sugerir alternativas**. Se implementó dentro de los endpoints que ya existían (`POST`/`PATCH /tasks`, ver [tareas.md](tareas.md)), en vez de un endpoint de "check" separado — así el frontend no tiene que acordarse de llamar a algo aparte antes de asignar.

- `crear_tarea` y la rama de group lead de `actualizar_tarea` en [task_service.py](../app/tasks/services/task_service.py) llaman a `advertencias_de_asignacion(organization, group, assignee_ids)` ([workload_service.py](../app/organizations/services/workload_service.py)) después de guardar la asignación.
- La asignación **nunca se bloquea** — la tarea se crea/edita igual, como pide el documento ("el sistema **puede advertir**", no "debe impedir").
- Si algún asignado queda `overloaded` **después** de esta asignación, la response trae un bloque `meta.warnings` adicional (no reemplaza `data`, JSON:API permite `meta` como info auxiliar al recurso):

```json
{
  "data": { "type": "tasks", "id": "12", "attributes": { "...": "..." } },
  "meta": {
    "warnings": [
      {
        "user_id": 5,
        "username": "ana",
        "active_task_count": 6,
        "detail": "ana está sobrecargado/a (6 tareas activas, umbral 5)",
        "suggested_alternatives": ["bruno", "caro"]
      }
    ]
  }
}
```

- `suggested_alternatives`: hasta 3 usernames de miembros del **mismo grupo** (cualquier rol, group lead o contributor) que estén `available` (0 tareas activas) y no sean ya parte de esta asignación.
- Solo se calculan advertencias cuando la request efectivamente trae `assignee_ids` — un `PATCH` que solo cambia `title` o un contributor cambiando `status` no dispara este chequeo (no cambió ninguna asignación).

## 5. Decisiones de diseño

- **Sin tabla propia**: Workload es 100% derivado de `Task`/`GroupMembership` existentes — cualquier tabla nueva solo duplicaría datos que ya hay que mantener sincronizados. Lo único persistente es el umbral.
- **Un solo umbral por organización, no por grupo**: el documento (RF-44) dice "el Owner configura el umbral de sobrecarga **de la organización**", no por grupo.
- **Advertencia integrada en los endpoints de tarea, no un endpoint de "check" aparte**: decisión tomada explícitamente para esta implementación — significa que cambiar la lógica de asignación de tareas también puede afectar el cálculo de advertencias; están acoplados a propósito.

## 6. Notas sobre el estado actual

- No hay notificación real (push/email/websocket) de las advertencias — viajan en la misma response HTTP del create/update de la tarea; es responsabilidad del frontend mostrarlas.
- La clasificación no distingue entre tareas "viejas" (muchos días en progreso) y recientes — es un conteo simple, no pondera por antigüedad ni por tamaño/complejidad de la tarea (el documento tampoco lo pide).
- Dependencias entre tareas (que podrían cambiar qué cuenta como "activa" — ej. una tarea bloqueada quizás no debería sumar a la carga) no están implementadas todavía; cuando se implementen, revisar si `ACTIVE_STATUSES` necesita ajustarse.
