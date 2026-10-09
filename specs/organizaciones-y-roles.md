# Organizaciones y roles

Spec técnico de las entidades `Organization` y `Membership`, base de la jerarquía Organización → Grupo → Proyecto → Tarea definida en el documento de especificación de Tasker (sección 2).

> Estado: modelo de datos + migración (aplicada contra la base Postgres real). Los servicios y endpoints (creación de organización, invitación, gestión de miembros, traspaso de owner) ya están implementados — ver [organizaciones-abm.md](organizaciones-abm.md).

## 1. Resumen

- App Django: `app/organizations`, registrada en `INSTALLED_APPS` como `app.organizations` (label `organizations`).
- Cubre el primer nivel de la jerarquía (Organización) y el rol a nivel organización (Owner / Admin / Member), correspondiente a la sección 2.2 "Nivel Organización" del documento de especificación.
- El rol **no** es un atributo del usuario: cuelga de la relación `Membership` entre `Users` y `Organization`, tal como especifica la sección 2.4 del documento ("A nivel de modelo de datos, esto se representa evitando que el rol sea un atributo del Usuario").
- Grupo y `Membresía_Grupo` (Group Lead / Contributor) quedan fuera de este spec — son la siguiente entidad a modelar.

## 2. Modelo de datos

### 2.1. `Organization`

[app/organizations/models/organization.py](../app/organizations/models/organization.py)

| Campo | Tipo | Notas |
|---|---|---|
| `name` | CharField(255) | Nombre de la organización |
| `invite_token` | UUIDField, unique, `default=uuid4` | Token del link de invitación único (sección 2.3 del doc, RF-09) |
| `invite_active` | BooleanField, `default=True` | Permite desactivar el link sin borrarlo (RF-10) |
| `plan` | CharField, choices `free` / `pro` | `default='free'` — corresponde a la sección 8.5 del doc |
| `plan_status` | CharField, choices `active` / `trial` / `expired` | `default='active'` |
| `created_at` | DateTimeField, `auto_now_add=True` | |

- Tabla: `organizations`.
- No tiene un campo `owner` directo: el owner es quien tiene la `Membership` con `role='owner'` en esa organización.

### 2.2. `Membership`

[app/organizations/models/membership.py](../app/organizations/models/membership.py)

| Campo | Tipo | Notas |
|---|---|---|
| `organization` | FK → `Organization`, `on_delete=CASCADE` | `related_name='memberships'` |
| `user` | FK → `Users` (`AUTH_USER_MODEL`), `on_delete=CASCADE` | `related_name='org_memberships'` |
| `role` | CharField, choices `owner` / `admin` / `member` | Sin default: se asigna explícitamente al crear la membership |
| `created_at` | DateTimeField, `auto_now_add=True` | |

- Tabla: `memberships`.
- `on_delete=CASCADE` en ambas FKs: si se borra la organización o el usuario, sus memberships se borran junto con él (no hay soft-delete todavía).

## 3. Reglas de negocio implementadas como constraints

| Constraint | Nombre | Regla |
|---|---|---|
| `UniqueConstraint(organization, user)` | `unique_membership_per_user_per_organization` | Un usuario tiene como máximo una membership (un solo rol) por organización — sección 2.4 del doc. |
| `UniqueConstraint(organization, condition=Q(role='owner'))` | `unique_owner_per_organization` | Nunca puede haber dos `owner` simultáneos en la misma organización. Existe para soportar el traspaso de rol (RF-14: el Owner transfiere su rol a otro miembro) sin permitir un estado inconsistente de dos owners a la vez. |

Estas reglas están a nivel de base de datos (constraints de Postgres), no solo a nivel de aplicación.

## 4. Relación con el documento de especificación

El modelo de datos de esta sección sostiene estos requerimientos funcionales; la lógica y los endpoints están documentados en [organizaciones-abm.md](organizaciones-abm.md):

| RF | Descripción | Cubierto por |
|---|---|---|
| RF-08 | Crear organización y asignar rol Owner automáticamente | `Organization` + `Membership(role='owner')` — servicio y endpoint en organizaciones-abm.md §2.1 |
| RF-09 | Generar/copiar link de invitación único | `Organization.invite_token` — endpoint en §2.6 |
| RF-10 | Desactivar o regenerar el link de invitación | `Organization.invite_active` — endpoints en §2.6 |
| RF-11, RF-12 | Unirse a una organización por link, con rol Member automático | `Membership(role='member')` — endpoint en §2.7 |
| RF-13 | Mostrar al usuario sin organización la opción de crear/unirse | Resuelto por `GET /organizations/` (§2.2): lista vacía → el frontend decide mostrar esa pantalla |
| RF-14 | Owner traspasa su rol a otro miembro | Constraint `unique_owner_per_organization` + lógica de traspaso en §2.9 |

No cubre todavía: nada del modelo de negocio de límites por plan (sección 8.5 del doc: validar plan/límite antes de acciones) — ver notas en organizaciones-abm.md §4.

## 5. Migración

[app/organizations/migrations/0001_initial.py](../app/organizations/migrations/0001_initial.py) — aplicada contra la base Postgres real (`python manage.py migrate organizations`).

## 6. Notas sobre el estado actual

- Los endpoints de creación, invitación, gestión de miembros y traspaso de Owner ya están implementados — ver [organizaciones-abm.md](organizaciones-abm.md).
- No hay validación de límites de plan (sección 8.5 del doc) antes de crear organización, invitar o unirse.
- `Group` y `GroupMembership` (Group Lead / Contributor) están modelados por separado — ver [grupos_y_roles/grupos-y-roles.md](grupos_y_roles/grupos-y-roles.md) — pero todavía no tienen ABM de endpoints propio.
