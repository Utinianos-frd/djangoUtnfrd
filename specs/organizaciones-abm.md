# ABM de organización y roles (endpoints)

Spec técnico de los endpoints de alta/baja/modificación de `Organization` y `Membership`. Complementa el modelo de datos ya documentado en [organizaciones-y-roles.md](organizaciones-y-roles.md) — ese spec queda desactualizado en su sección 6 ("no implementado"): los endpoints que ahí se listaban como pendientes ya existen y se documentan acá.

> Probado end-to-end contra la base Postgres real (crear, listar, ver, editar, invitar, unirse, listar miembros, traspasar owner, bloquear baja del owner, eliminar organización) — no solo `manage.py check`.

## 1. Resumen

- Base URL: `/api/v1/organizations/`.
- Todos requieren autenticación JWT (`IsAuthenticated`, el default de `REST_FRAMEWORK`) excepto que se indique lo contrario.
- Todos siguen JSON:API, igual que `app/users` — ver [sistema-logueo.md](login/sistema-logueo.md) para el formato general y el de errores.
- Autorización: no hay `permission_classes` por endpoint más allá de `IsAuthenticated` — el chequeo de rol (owner/admin/member dentro de *esa* organización puntual) se hace a mano en cada función de servicio con el helper `get_role(user, organization)` ([common.py](../app/organizations/services/common.py)), siguiendo el mismo patrón de `app/users/services/auth_service.py` (lógica de negocio en el service, vista como wrapper fino). Se eligió así en vez de una `permission_class` de DRF porque el permiso depende del *objeto* (¿sos owner de *esta* organización?), no es un chequeo global.

## 2. Endpoints

| Método | Path | Quién puede | RF / sección del doc |
|---|---|---|---|
| POST | `/organizations/` | Cualquier usuario autenticado | RF-08 |
| GET | `/organizations/` | Cualquier usuario autenticado (lista las propias) | RF-13 (parcial) |
| GET | `/organizations/{id}` | Miembro de la organización | — |
| PATCH | `/organizations/{id}` | Owner | — |
| DELETE | `/organizations/{id}` | Owner | matriz 3.1 "Borrar la organización" |
| GET | `/organizations/{id}/invite` | Owner o Admin | matriz 3.1 "Invitar miembros" |
| POST | `/organizations/{id}/invite/regenerate` | Owner | RF-10 |
| POST | `/organizations/{id}/invite/deactivate` | Owner | RF-10 |
| POST | `/organizations/join` | Cualquier usuario autenticado | RF-11, RF-12 |
| GET | `/organizations/{id}/members` | Miembro de la organización | — |
| PATCH | `/organizations/{id}/members/{user_id}` | Owner | matriz 3.1 "Cambiar roles", RF-14 |
| DELETE | `/organizations/{id}/members/{user_id}` | Owner o Admin | matriz 3.1 "Eliminar miembros" |

### 2.1. `POST /organizations/` — crear organización

Crea la `Organization` y, en la misma operación, la `Membership` del usuario autenticado con `role='owner'` (RF-08: "asignarle automáticamente el rol de Owner").

**Request**
```json
{ "data": { "type": "organizations", "attributes": { "name": "Mi Equipo" } } }
```

**Response 201**
```json
{
  "data": {
    "type": "organizations",
    "id": "1",
    "attributes": { "name": "Mi Equipo", "plan": "free", "plan_status": "active", "role": "owner" }
  }
}
```

`role` en la respuesta es el rol del usuario que hizo el request en esa organización (no un campo de `Organization` — se resuelve en cada response, ver [`_organization_resource`](../app/organizations/services/organization_service.py)).

**Errores**: `400` si falta el body JSON:API o `name`.

### 2.2. `GET /organizations/` — listar mis organizaciones

Devuelve todas las organizaciones donde el usuario autenticado tiene una `Membership`, con su rol en cada una. Es la data que resuelve RF-13 ("mostrar al usuario sin organización la opción de crear o unirse"): si `data` viene vacío, el frontend muestra esa pantalla.

**Response 200**
```json
{ "data": [ { "type": "organizations", "id": "1", "attributes": { "name": "Mi Equipo", "plan": "free", "plan_status": "active", "role": "owner" } } ] }
```

### 2.3. `GET /organizations/{id}` — detalle

Igual estructura que el item de la lista. **Errores**: `404` si no existe la organización, `403` si el usuario no es miembro (no se distingue "no existe" de "no tenés acceso" más que por el código — se devuelve 404 real cuando no existe, 403 cuando existe pero no pertenecés).

### 2.4. `PATCH /organizations/{id}` — editar

Por ahora solo permite cambiar `name` (único campo editable del dominio; `plan`/`plan_status` quedan fuera de este ABM, ver sección 5).

**Request**: igual forma que el create, con los campos a cambiar. **Errores**: `404`, `403` (no-owner).

### 2.5. `DELETE /organizations/{id}` — eliminar

Borra la organización. Por `on_delete=CASCADE` en los modelos, se llevan puestos en cascada sus `Membership`, `Group` y `GroupMembership` (ver [organizaciones-y-roles.md](organizaciones-y-roles.md) y [grupos_y_roles/grupos-y-roles.md](grupos_y_roles/grupos-y-roles.md)). **Response**: `204` sin body. **Errores**: `404`, `403` (no-owner).

### 2.6. Invitación — `GET/POST .../invite`, `.../invite/regenerate`, `.../invite/deactivate`

```json
{ "data": { "type": "invitations", "id": "<uuid>", "attributes": { "token": "<uuid>", "active": true } } }
```

- `GET invite`: ver el token y si está activo. Owner o Admin (matriz: "Invitar miembros" lo pueden ambos).
- `POST invite/regenerate`: genera un `invite_token` nuevo (invalida el anterior) y fuerza `invite_active=true`. Solo Owner (RF-10 lo liga a la misma acción que crear grupos/asignar roles, atribuciones exclusivas del Owner).
- `POST invite/deactivate`: pone `invite_active=false` sin tocar el token. Solo Owner.

**Errores**: `404` (org inexistente), `403` (rol insuficiente).

### 2.7. `POST /organizations/join` — unirse por link

```json
{ "data": { "type": "invitations", "attributes": { "token": "<uuid>" } } }
```

Busca una organización con ese `invite_token` y `invite_active=true`, y crea una `Membership(role='member')` para el usuario autenticado (RF-11, RF-12).

**Response 201**: mismo formato que el detalle de organización, con `role: "member"`.

**Errores**: `400` (falta `token` o no es un UUID válido), `404` (token inválido o `invite_active=false` — no se distingue "no existe" de "desactivado", ambos devuelven el mismo 404 genérico para no filtrar información del estado del link), `409` (el usuario ya pertenece a esa organización).

### 2.8. `GET /organizations/{id}/members` — listar miembros

Cualquier miembro (cualquier rol) puede ver la lista completa, con `user_id`, `username` y `role` de cada uno.

```json
{ "data": [ { "type": "memberships", "id": "2", "attributes": { "user_id": 4, "username": "ana", "role": "member" } } ] }
```

### 2.9. `PATCH /organizations/{id}/members/{user_id}` — cambiar rol (incluye traspaso de Owner, RF-14)

```json
{ "data": { "type": "memberships", "attributes": { "role": "admin" } } }
```

Reglas de negocio (no triviales, ver [membership_service.cambiar_rol_miembro](../app/organizations/services/membership_service.py)):

1. Solo el Owner puede usar este endpoint (matriz: "Cambiar roles" — ni siquiera el Admin puede).
2. **No se puede bajar al Owner actual a otro rol directamente.** Si `target.role == 'owner'` y se pide un `role` distinto, el sistema rechaza con `400`. La única forma de que el Owner deje de serlo es traspasando el puesto (punto siguiente).
3. **Traspaso de Owner**: si el `role` pedido es `'owner'` (para un miembro que no lo es), el sistema busca a quien tenga `role='owner'` en esa organización y lo pasa a `role='admin'` automáticamente, antes de asignarle `'owner'` al nuevo. Así nunca hay un instante con dos owners ni con cero (y la constraint `unique_owner_per_organization` de la DB queda siempre satisfecha). Esto responde la pregunta que el documento de especificación no contestaba: **el owner saliente queda como admin**, no se queda sin rol administrativo.

**Errores**: `404` (org o membership del `user_id` inexistente), `403` (quien pide no es owner), `400` (intento de bajar al owner directamente, o `role` inválido).

### 2.10. `DELETE /organizations/{id}/members/{user_id}` — eliminar miembro

Owner o Admin (matriz: "Eliminar miembros"). **No se puede eliminar a quien tiene `role='owner'`** — primero hay que traspasar el rol (punto 2.9) y después sí se lo puede eliminar como admin/member. **Response**: `204`. **Errores**: `404`, `403`, `400` (target es owner).

## 3. Decisiones de diseño

- **Un solo campo mutable en `Organization` vía PATCH (`name`)**: `plan`/`plan_status`/`invite_token`/`invite_active` tienen sus propias reglas (billing, regeneración) y no deberían poder pisarse con un PATCH genérico — por eso invite tiene sus propios endpoints de acción en vez de ser parte del PATCH.
- **Autorización en el service, no en una `permission_class`**: ver sección 1. Si en el futuro se repite mucho este patrón entre apps (organizations, y más adelante tasks), vale la pena extraerlo a una `permission_class` reutilizable tipo `HasOrganizationRole(*roles)` — hoy no se justifica todavía (dos servicios, patrón simple).
- **`join` devuelve 404 unificado para token inexistente o desactivado**: decisión deliberada para no revelarle a quien prueba tokens al azar si un link "existió pero fue desactivado" vs "nunca existió".

## 4. Notas sobre el estado actual

- No hay endpoint para que un miembro "se vaya" de una organización por su cuenta (leave) — hoy solo Owner/Admin pueden sacar a otros vía DELETE members. No estaba en el alcance pedido para esta tanda.
- No hay validación de límites de plan (sección 8.5 del documento: tope de miembros/grupos del plan Free) antes de `join` o `crear_organizacion` — sigue pendiente, como ya estaba anotado en [organizaciones-y-roles.md](organizaciones-y-roles.md).
- Los schemas de OpenAPI (`@extend_schema`) de estos endpoints son más livianos que los de `app/users` (sin ejemplos de request/response inline) — doce endpoints con el mismo nivel de detalle que login/register hubiera sido desproporcionado para esta tanda; si hace falta documentación más rica en Swagger, se puede sumar después sin tocar la lógica.
