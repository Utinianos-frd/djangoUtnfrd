# Grupos y roles de grupo

Spec técnico de las entidades `Group` y `GroupMembership`, segundo nivel de la jerarquía Organización → Grupo → Proyecto → Tarea. Complementa [organizaciones-y-roles.md](organizaciones-y-roles.md).

> Estado: solo modelo de datos + migración. No hay servicios ni endpoints todavía.

## 1. Resumen

- Viven en la misma app `app/organizations` que `Organization`/`Membership` (decisión: Grupo es jerarquía organizacional, no gestión de trabajo — `app/tasks` queda reservada para Proyecto/Tarea/Dependencia).
- Cubre la sección 2.2 "Nivel Grupo" del documento de especificación: rol **Group Lead** (responsable del grupo, arma el equipo, crea y asigna tareas) y **Contributor** (ejecuta tareas asignadas).
- Igual que a nivel organización, el rol de grupo no es un atributo del usuario ni del grupo: cuelga de `GroupMembership`, la relación entre `Users` y `Group` (sección 2.4 del doc).
- Un usuario puede pertenecer a más de un grupo simultáneamente, incluso con roles distintos en cada uno (ej. Group Lead del Grupo 1 y Contributor del Grupo 2) — sección 2.4 y RF-19.

## 2. Modelo de datos

### 2.1. `Group`

[app/organizations/models/group.py](../app/organizations/models/group.py)

| Campo | Tipo | Notas |
|---|---|---|
| `organization` | FK → `Organization`, `on_delete=CASCADE` | `related_name='groups'` |
| `name` | CharField(255) | Nombre del grupo |
| `created_at` | DateTimeField, `auto_now_add=True` | |

- Tabla: `groups`.
- `on_delete=CASCADE`: si se borra la organización, se borran sus grupos. Corresponde a RF-16 en cadena (Owner elimina un grupo → se eliminan en cascada sus proyectos y tareas; acá se modela el primer nivel de esa cascada).
- No tiene un campo `group_lead` directo: el líder es quien tiene la `GroupMembership` con `role='group_lead'` en ese grupo.

### 2.2. `GroupMembership`

[app/organizations/models/group_membership.py](../app/organizations/models/group_membership.py)

| Campo | Tipo | Notas |
|---|---|---|
| `group` | FK → `Group`, `on_delete=CASCADE` | `related_name='memberships'` |
| `user` | FK → `Users` (`AUTH_USER_MODEL`), `on_delete=CASCADE` | `related_name='group_memberships'` |
| `role` | CharField, choices `group_lead` / `contributor` | Sin default: se asigna explícitamente |
| `created_at` | DateTimeField, `auto_now_add=True` | |

- Tabla: `group_memberships`.

## 3. Reglas de negocio implementadas como constraints

| Constraint | Nombre | Regla |
|---|---|---|
| `UniqueConstraint(group, user)` | `unique_membership_per_user_per_group` | Un usuario tiene como máximo un rol por grupo (no puede ser Group Lead y Contributor del mismo grupo a la vez). |
| `UniqueConstraint(group, condition=Q(role='group_lead'))` | `unique_group_lead_per_group` | Nunca puede haber dos Group Lead simultáneos en el mismo grupo, reflejando "el Owner asigna un Group Lead a cada grupo" (singular) de la sección 2.3 del doc. |

Ambas a nivel de base de datos (constraints de Postgres).

### 3.1. Reglas de negocio **no** cubiertas por constraints de DB (quedan para la capa de servicio)

- Un `GroupMembership` debería requerir que el usuario ya sea `Member` de la `Organization` dueña del `Group` (RF-17: "el Group Lead agrega Members de la organización a su grupo"). No hay FK ni constraint que lo garantice a nivel de esquema — es una validación cruzada entre `Membership` y `GroupMembership` que se implementará en el servicio de alta.
- Solo el Owner puede asignar el rol de Group Lead (RF-15) y solo el Group Lead puede agregar/remover miembros de su propio grupo (RF-17, RF-18) — autorización, no modelo de datos.

## 4. Relación con el documento de especificación

| RF | Descripción | Cubierto por el modelo |
|---|---|---|
| RF-14 (bis) | Owner crea grupos dentro de la organización | `Group` — falta el servicio/endpoint |
| RF-15 | Owner asigna rol de Group Lead a un Member, dentro de un grupo | `GroupMembership(role='group_lead')` + constraint de unicidad — falta el servicio |
| RF-16 | Owner elimina un grupo (cascada proyectos y tareas) | `on_delete=CASCADE` en `Group.organization` cubre el borrado del grupo en sí; la cascada hacia Proyecto/Tarea se resolverá cuando existan esos modelos |
| RF-17 | Group Lead agrega Members de la organización a su grupo | `GroupMembership(role='contributor')` — falta la validación cruzada con `Membership` y el endpoint |
| RF-18 | Group Lead remueve miembros de su grupo (se reasignan sus tareas) | Falta completo: borrar `GroupMembership` es trivial, pero la reasignación de tareas depende del modelo de Tarea, que no existe todavía |
| RF-19 | Un miembro puede pertenecer a más de un grupo simultáneamente | Sin restricción que lo impida — un usuario puede tener múltiples `GroupMembership` en distintos `Group` |

## 5. Migración

[app/organizations/migrations/0002_group_groupmembership_and_more.py](../app/organizations/migrations/0002_group_groupmembership_and_more.py) — generada, no aplicada contra la base Postgres real.

## 6. Notas sobre el estado actual

- No hay servicio/endpoint para crear grupos (RF-14 bis), asignar Group Lead (RF-15), eliminar grupos (RF-16), ni gestionar miembros del grupo (RF-17, RF-18).
- No hay validación que impida agregar a un `Group` a un usuario que no sea `Member` de la `Organization` correspondiente (ver 3.1).
- La cascada de borrado de `Group` → Proyectos → Tareas (RF-16) solo está resuelta hasta donde existen modelos: falta modelar `Project` y `Task`.
- `Proyecto` y `Tarea` (con sus dependencias) siguen sin modelar — son el siguiente nivel de la jerarquía.
