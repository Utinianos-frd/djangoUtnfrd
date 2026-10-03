# Organizaciones y roles

Spec técnico de las entidades `Organization` y `Membership`, base de la jerarquía Organización → Grupo → Proyecto → Tarea definida en el documento de especificación de Tasker (sección 2).

> Estado: solo modelo de datos + migración. Todavía no hay servicios, endpoints ni lógica de negocio (creación de organización, invitación, traspaso de owner). Esa lógica se especificará por separado cuando se implemente.

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

Cubre parcialmente estos requerimientos funcionales (modelo de datos únicamente, falta la lógica/endpoints):

| RF | Descripción | Cubierto por el modelo |
|---|---|---|
| RF-08 | Crear organización y asignar rol Owner automáticamente | `Organization` + `Membership(role='owner')` — falta el servicio que los crea juntos |
| RF-09 | Generar/copiar link de invitación único | `Organization.invite_token` |
| RF-10 | Desactivar o regenerar el link de invitación | `Organization.invite_active` (falta endpoint de regeneración) |
| RF-11, RF-12 | Unirse a una organización por link, con rol Member automático | Requiere `Membership(role='member')` — falta el endpoint que resuelve el token |
| RF-14 | Owner traspasa su rol a otro miembro | Habilitado por el constraint `unique_owner_per_organization` — falta el servicio que hace el traspaso |

No cubre todavía: RF-13 (pantalla de "sin organización"), ni nada del modelo de negocio de límites por plan (sección 8.5 del doc: validar plan/límite antes de acciones).

## 5. Migración

[app/organizations/migrations/0001_initial.py](../app/organizations/migrations/0001_initial.py) — `python manage.py makemigrations organizations`, generada pero **no aplicada** (no se corrió `migrate` contra la base Postgres del `docker-compose`).

## 6. Notas sobre el estado actual

Explícitamente no implementado en esta tanda (fuera de alcance de este spec, no del proyecto):

- No hay servicio/endpoint para crear una organización (RF-08).
- No hay endpoint para generar, ver o regenerar el link de invitación (RF-09, RF-10).
- No hay endpoint para unirse a una organización vía link (RF-11, RF-12).
- No hay endpoint para invitar, eliminar o cambiar el rol de un miembro (sección 3.1 del doc).
- No hay endpoint para traspasar el rol de Owner (RF-14).
- No hay validación de límites de plan (sección 8.5 del doc).
- `Group` y `Membership` a nivel de grupo (Group Lead / Contributor) no están modelados todavía.
