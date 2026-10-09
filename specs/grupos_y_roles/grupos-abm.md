# ABM de grupo y roles de grupo (endpoints)

Spec técnico de los endpoints de alta/baja/modificación de `Group` y `GroupMembership`. Complementa el modelo de datos documentado en [grupos-y-roles.md](grupos-y-roles.md) (desactualizado en su sección de "no implementado": esos endpoints ya existen y se documentan acá) y sigue el mismo patrón de [organizaciones-abm.md](../organizaciones-abm.md).

> Probado end-to-end contra la base Postgres real, incluyendo el caso límite del bootstrap del primer group lead (ver sección 3).

## 1. Resumen

- Base URL: `/api/v1/organizations/{organization_id}/groups/...` (anidado bajo la organización dueña del grupo).
- Todos requieren autenticación JWT. JSON:API, mismo formato de errores que el resto de la API.
- Autorización resuelta a mano en cada función de servicio, igual que en `organizaciones-abm.md` — ver [common.py](../../app/organizations/services/common.py), [group_service.py](../../app/organizations/services/group_service.py), [group_membership_service.py](../../app/organizations/services/group_membership_service.py).

## 2. Endpoints

| Método | Path | Quién puede | RF / matriz |
|---|---|---|---|
| POST | `/groups` | Owner | RF-14 (bis) |
| GET | `/groups` | Cualquier miembro de la organización (ve todos si es owner/admin, solo los suyos si es member) | matriz 3.1 "Ver todos los grupos" vs "Ver grupo/s al que pertenece" |
| GET | `/groups/{id}` | Owner/admin, o miembro de ese grupo | — |
| PATCH | `/groups/{id}` | Owner | — |
| DELETE | `/groups/{id}` | Owner | RF-16 |
| GET | `/groups/{id}/members` | Owner/admin, o miembro de ese grupo | — |
| POST | `/groups/{id}/members` | Group lead del grupo | RF-17 |
| PATCH | `/groups/{id}/members/{user_id}` | Owner de la organización | RF-15 |
| DELETE | `/groups/{id}/members/{user_id}` | Group lead del grupo | RF-18 |

**Lectura literal de la matriz (sección 3.2 del documento)**: la tabla de permisos a nivel grupo solo tiene columnas Group Lead / Contributor — ni Owner ni Admin aparecen ahí para "agregar miembros al grupo" o "gestionar el grupo". Por eso alta/baja de miembros del grupo es exclusiva del Group Lead; el Owner controla la estructura (crear/eliminar grupos, asignar quién es el Group Lead) pero no agrega gente directamente al día a día de un grupo — salvo la excepción explicada en la sección 3.

### 2.1. `POST /groups` — crear grupo

```json
{ "data": { "type": "groups", "attributes": { "name": "Backend" } } }
```

**Response 201**
```json
{ "data": { "type": "groups", "id": "1", "attributes": { "name": "Backend", "organization_id": 3 } } }
```

**Errores**: `404` (organización inexistente), `403` (no-owner), `400` (falta `name`).

### 2.2. `GET /groups` — listar grupos de la organización

Owner y Admin ven **todos** los grupos de la organización. Member ve **solo** los grupos donde tiene una `GroupMembership` (cualquier rol). Implementado filtrando por `memberships__user=request.user` cuando el rol de organización es `member`.

### 2.3-2.5. `GET` / `PATCH` / `DELETE /groups/{id}`

Mismo patrón que `organizations/{id}` (ver organizaciones-abm.md §2.3-2.5). `DELETE` arrastra en cascada `GroupMembership` y `Project` (y lo que éstos arrastren) por `on_delete=CASCADE`.

### 2.6. `GET /groups/{id}/members` — listar miembros del grupo

Visible para Owner/Admin de la organización, o cualquier miembro del grupo (group lead o contributor).

```json
{ "data": [ { "type": "group_memberships", "id": "1", "attributes": { "user_id": 5, "username": "ana", "role": "contributor" } } ] }
```

### 2.7. `POST /groups/{id}/members` — agregar miembro al grupo

```json
{ "data": { "type": "group_memberships", "attributes": { "user_id": 5 } } }
```

Solo el **group lead** del grupo. Siempre crea la membership con `role='contributor'` — para asignar `group_lead` existe un endpoint separado (§2.8), igual que en organizaciones (crear vs. transferir ownership son acciones distintas).

**Validación agregada que antes faltaba** (estaba anotada como pendiente en [grupos-y-roles.md §3.1](grupos-y-roles.md)): el `user_id` debe ya ser `Member` de la organización dueña del grupo (`Membership` existente), si no, `400`. Esto es justamente lo que pide RF-17: "el Group Lead agrega **Members de la organización** a su grupo", no cualquier usuario del sistema.

**Errores**: `404` (grupo inexistente), `403` (quien pide no es group lead), `400` (falta `user_id`, o el usuario no es miembro de la organización), `409` (ya pertenece al grupo).

### 2.8. `PATCH /groups/{id}/members/{user_id}` — asignar rol de grupo (incluye group lead, RF-15)

```json
{ "data": { "type": "group_memberships", "attributes": { "role": "group_lead" } } }
```

Solo el **Owner de la organización** (no el group lead, no el admin — coherente con que asignar Group Lead es una decisión de estructura, igual que crear el grupo). Mismas reglas que el traspaso de Owner en organizaciones-abm.md §2.9:

- No se puede bajar al group lead actual a otro rol directamente (`400`) — hay que asignarle `group_lead` a otra persona primero.
- Asignar `role='group_lead'` a alguien pasa automáticamente al group lead anterior (si existe) a `role='contributor'`.

**Caso especial de bootstrap** (ver sección 3): a diferencia del resto de los endpoints de esta tabla, este **no requiere que el usuario ya tenga una `GroupMembership`** — si no la tiene, se crea en el momento con el rol pedido. Es la única puerta de entrada para que alguien llegue a ser el primer group lead de un grupo recién creado.

**Errores**: `404` (grupo inexistente), `403` (no-owner), `400` (usuario no es miembro de la organización, `role` inválido, o intento de bajar al group lead directamente).

### 2.9. `DELETE /groups/{id}/members/{user_id}` — eliminar miembro del grupo

Solo el group lead. No se puede eliminar al propio group lead (hay que reasignar el rol primero vía §2.8). RF-18 menciona que al remover un miembro se reasignan sus tareas — no implementado todavía porque `Task` no existe (ver notas).

## 3. Bug de bootstrap encontrado y corregido

Al probar el flujo completo end-to-end apareció un problema real: **nadie podía convertirse en el primer group lead de un grupo nuevo.**

- `POST /groups/{id}/members` (agregar miembro) exige que quien llama ya sea group lead.
- La primera versión de `PATCH /groups/{id}/members/{user_id}` (asignar rol) exigía que el `GroupMembership` **ya existiera** — pero la única forma de crearlo era el endpoint anterior.

Resultado: un grupo recién creado por el Owner quedaba sin forma de tener group lead por API. Se corrigió haciendo que el `PATCH` de asignación de rol (único endpoint reservado al Owner, no al group lead) cree la `GroupMembership` si no existe, en vez de devolver `404`. Esto no abre ningún agujero de seguridad nuevo: sigue siendo exclusivo del Owner, y sigue validando que el usuario sea `Member` de la organización antes de crear la fila.

Encontrado y corregido mediante el smoke test end-to-end contra la base real, no solo por inspección de código.

## 4. Notas sobre el estado actual

- RF-18 ("al remover un miembro del grupo se reasignan sus tareas") no está implementado: `Task` todavía no existe como modelo.
- No hay límite de cantidad de grupos por organización todavía (sección 8.5 del documento, plan Free: "1 Grupo por organización") — pendiente, igual que en organizaciones-abm.md.
