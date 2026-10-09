# Grupos y roles de grupo

Spec técnico de las entidades `Group` y `GroupMembership`, segundo nivel de la jerarquía Organización → Grupo → Proyecto → Tarea. Complementa [organizaciones-y-roles.md](../organizaciones-y-roles.md).

> Estado: modelo de datos + migración (aplicada contra la base Postgres real). Los servicios y endpoints (crear grupo, asignar group lead, agregar/quitar miembros) ya están implementados — ver [grupos-abm.md](grupos-abm.md).

## 1. Resumen

- Viven en la misma app `app/organizations` que `Organization`/`Membership` (decisión: Grupo es jerarquía organizacional, no gestión de trabajo — `app/tasks` queda reservada para Proyecto/Tarea/Dependencia).
- Cubre la sección 2.2 "Nivel Grupo" del documento de especificación: rol **Group Lead** (responsable del grupo, arma el equipo, crea y asigna tareas) y **Contributor** (ejecuta tareas asignadas).
- Igual que a nivel organización, el rol de grupo no es un atributo del usuario ni del grupo: cuelga de `GroupMembership`, la relación entre `Users` y `Group` (sección 2.4 del doc).
- Un usuario puede pertenecer a más de un grupo simultáneamente, incluso con roles distintos en cada uno (ej. Group Lead del Grupo 1 y Contributor del Grupo 2) — sección 2.4 y RF-19.

## 2. Modelo de datos

### 2.1. `Group`

[app/organizations/models/group.py](../../app/organizations/models/group.py)

| Campo | Tipo | Notas |
|---|---|---|
| `organization` | FK → `Organization`, `on_delete=CASCADE` | `related_name='groups'` |
| `name` | CharField(255) | Nombre del grupo |
| `created_at` | DateTimeField, `auto_now_add=True` | |

- Tabla: `groups`.
- `on_delete=CASCADE`: si se borra la organización, se borran sus grupos. Corresponde a RF-16 en cadena (Owner elimina un grupo → se eliminan en cascada sus proyectos y tareas; acá se modela el primer nivel de esa cascada).
- No tiene un campo `group_lead` directo: el líder es quien tiene la `GroupMembership` con `role='group_lead'` en ese grupo.

### 2.2. `GroupMembership`

[app/organizations/models/group_membership.py](../../app/organizations/models/group_membership.py)

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

### 3.1. Reglas de negocio que viven en la capa de servicio (no en constraints de DB)

- Un `GroupMembership` requiere que el usuario ya sea `Member` de la `Organization` dueña del `Group` (RF-17) — validado en `agregar_miembro_grupo`, ver [grupos-abm.md §2.7](grupos-abm.md).
- Solo el Owner puede asignar el rol de Group Lead (RF-15) y solo el Group Lead puede agregar/remover miembros de su propio grupo (RF-17, RF-18) — ver [grupos-abm.md](grupos-abm.md) para el detalle, incluyendo un caso de bootstrap no trivial (§3 de ese spec).

## 4. Relación con el documento de especificación

El modelo de datos de esta sección sostiene estos requerimientos funcionales; la lógica y los endpoints están documentados en [grupos-abm.md](grupos-abm.md):

| RF | Descripción | Cubierto por |
|---|---|---|
| RF-14 (bis) | Owner crea grupos dentro de la organización | `Group` — endpoint en grupos-abm.md §2.1 |
| RF-15 | Owner asigna rol de Group Lead a un Member, dentro de un grupo | `GroupMembership(role='group_lead')` + constraint de unicidad — endpoint en §2.8 |
| RF-16 | Owner elimina un grupo (cascada proyectos y tareas) | `on_delete=CASCADE` en `Group.organization` y en `Project.group` — endpoint en §2.5 |
| RF-17 | Group Lead agrega Members de la organización a su grupo | `GroupMembership(role='contributor')` — endpoint en §2.7 |
| RF-18 | Group Lead remueve miembros de su grupo (se reasignan sus tareas) | Baja del miembro: endpoint en §2.9. Reasignación de tareas: pendiente, depende de `Task` |
| RF-19 | Un miembro puede pertenecer a más de un grupo simultáneamente | Sin restricción que lo impida — un usuario puede tener múltiples `GroupMembership` en distintos `Group` |

## 5. Migración

[app/organizations/migrations/0002_group_groupmembership_and_more.py](../../app/organizations/migrations/0002_group_groupmembership_and_more.py) — aplicada contra la base Postgres real.

## 6. Notas sobre el estado actual

- Los endpoints de creación, asignación de Group Lead y gestión de miembros ya están implementados — ver [grupos-abm.md](grupos-abm.md).
- La reasignación automática de tareas al remover un miembro (RF-18) sigue pendiente: depende de que exista `Task`.
- `Proyecto` ya está modelado — ver [proyectos.md](../proyectos.md). `Tarea` (con sus dependencias) sigue sin modelar.
