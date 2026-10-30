# Sistema de logueo

Spec técnico del sistema de autenticación actual del proyecto. Documenta el comportamiento tal como está implementado en [app/users/](../../app/users/), no propone cambios.

## 1. Resumen

- **Framework**: Django 5.0 + Django REST Framework 3.16.
- **Autenticación**: JWT vía `djangorestframework-simplejwt` 5.5. No hay sesiones ni cookies involucradas en la API; el cliente guarda `access`/`refresh` y los envía como header.
- **Formato de request/response**: todos los endpoints de auth siguen la convención [JSON:API](https://jsonapi.org/) (`{ "data": { "type", "attributes" } }`), incluyendo los errores, **excepto** `token/refresh`, que usa el formato nativo de `simplejwt` (ver [4.3](#43-post-apiv1authtokenrefresh)).
- **Documentación autogenerada**: Swagger/Redoc vía `drf-spectacular`, disponible en `/api/v1/docs/` y `/api/v1/redoc/`. Este spec complementa esa referencia con reglas de negocio, modelo de datos y seguridad que el schema OpenAPI no cubre.
- **Base URL**: `/api/v1/auth/` (definida en [config/urls.py](../../config/urls.py)).

## 2. Modelo de datos

`Users` extiende `AbstractUser` de Django ([app/users/models/users.py](../../app/users/models/users.py)):

| Campo      | Tipo         | Constraints                    |
|------------|--------------|---------------------------------|
| `username` | CharField    | `max_length=255`, `unique=True` |
| `email`    | EmailField   | `unique=True`                   |
| `password` | CharField    | `max_length=255` (hasheado por Django, no en texto plano) |
| `role`     | CharField    | `max_length=50`, sin default ni choices explícitos; se asigna `'user'` al registrar |

- Tabla: `users` (`db_table = 'users'`).
- Configurado como modelo de usuario del proyecto: `AUTH_USER_MODEL = 'users.Users'` (config/settings.py:75).
- Hereda de `AbstractUser`, por lo que también tiene `is_active`, `is_staff`, `is_superuser`, `date_joined`, etc., aunque no se usan explícitamente en la lógica de auth actual.

## 3. Endpoints

Rutas definidas en [app/users/urls.py](../../app/users/urls.py):

| Método | Path                          | Auth requerida    | Vista |
|--------|-------------------------------|-------------------|-------|
| POST   | `/api/v1/auth/login`          | No (`AllowAny`)   | `login` |
| POST   | `/api/v1/auth/register`       | No (`AllowAny`)   | `register` |
| POST   | `/api/v1/auth/token/refresh`  | No (requiere refresh token válido) | `TokenRefreshView` (simplejwt) |
| GET    | `/api/v1/auth/me`             | Sí (`IsAuthenticated`) | `me` |

### 3.1. `POST /api/v1/auth/login`

Autentica un usuario existente y devuelve un par de tokens.

**Request**
```json
{
  "data": {
    "type": "sessions",
    "attributes": {
      "username": "alex",
      "password": "secret123"
    }
  }
}
```
- `username` y `password` son obligatorios.

**Response 200**
```json
{
  "data": {
    "type": "sessions",
    "attributes": {
      "access": "<jwt_access_token>",
      "refresh": "<jwt_refresh_token>",
      "exp": "2026-05-23T18:45:00Z"
    }
  }
}
```
- `exp` es el vencimiento del **access token**, en UTC ISO 8601.

**Errores**
- `400` — body no sigue estructura JSON:API, o falta `username`/`password`.
- `401` — credenciales inválidas (`authenticate()` de Django devuelve `None`).

Lógica: [auth_service.login_usuario](../../app/users/services/auth_service.py#L19).

### 3.2. `POST /api/v1/auth/register`

Crea un usuario nuevo con `role='user'` y devuelve tokens (login automático post-registro).

**Request**
```json
{
  "data": {
    "type": "users",
    "attributes": {
      "username": "alex",
      "email": "alex@example.com",
      "password": "secret123"
    }
  }
}
```
- Validado por `RegisterSerializer` ([app/users/serializers/register_serializer.py](../../app/users/serializers/register_serializer.py)):
  - `username`: string, `max_length=150`.
  - `email`: formato email válido.
  - `password`: string, `min_length=8`, `write_only`.
- La única regla sobre la password es la del serializer (`min_length=8`). **No** pasa por los `AUTH_PASSWORD_VALIDATORS` de Django: `create_user` no los ejecuta (solo los usan los formularios de Django y `validate_password`), así que passwords como `12345678` se aceptan. Decisión explícita: se deja así.

**Response 201**
```json
{
  "data": {
    "type": "sessions",
    "attributes": {
      "access": "<jwt_access_token>",
      "refresh": "<jwt_refresh_token>"
    }
  }
}
```
- A diferencia del login, esta respuesta **no incluye `exp`**.

**Errores**
- `400` — body no sigue estructura JSON:API, o falla la validación del serializer (errores con `source.pointer` apuntando al atributo, ej. `/data/attributes/email`).
- `409` — `username` ya existe, o `email` ya está registrado (se chequean por separado, primero username).

Lógica: [auth_service.register_usuario](../../app/users/services/auth_service.py#L48).

### 3.3. `POST /api/v1/auth/token/refresh`

Vista estándar de `simplejwt` (`TokenRefreshView`), **no pasa por `auth_service`** y por lo tanto **no sigue el formato JSON:API**.

**Request**
```json
{ "refresh": "<jwt_refresh_token>" }
```

**Response 200**
```json
{ "access": "<jwt_access_token>" }
```
- `ROTATE_REFRESH_TOKENS` no está configurado (default `False`), por lo que el refresh token no rota ni se devuelve uno nuevo.

**Errores**
- `401` — refresh token inválido o expirado (formato de error nativo de simplejwt, no JSON:API).

### 3.4. `GET /api/v1/auth/me`

Devuelve el perfil del usuario autenticado. Requiere header `Authorization: Bearer <access_token>`.

**Response 200**
```json
{
  "data": {
    "type": "users",
    "id": "1",
    "attributes": {
      "username": "alex",
      "email": "alex@example.com",
      "role": "user"
    },
    "links": {
      "self": "/api/v1/auth/me"
    }
  }
}
```

**Errores**
- `401` — sin token o token inválido/expirado (manejado por `IsAuthenticated` + `JWTAuthentication`, no por `auth_service`).

Lógica: [auth_service.get_perfil_usuario](../../app/users/services/auth_service.py#L88).

## 4. Flujos

### 4.1. Login
```
Cliente                          API                              DB
   |--- POST /auth/login -------->|                                 |
   |    { username, password }    |--- authenticate(username,pwd) ->|
   |                               |<-- User o None ------------------|
   |                               |--- (si válido) genera JWT        |
   |<-- 200 { access, refresh, exp } / 401 { errors } ---------------|
```

### 4.2. Registro
```
Cliente                          API                              DB
   |--- POST /auth/register ----->|                                 |
   |    { username, email, pwd }  |--- valida serializer             |
   |                               |--- chequea username/email únicos -> DB
   |                               |--- create_user(role='user') ---->|
   |                               |--- genera JWT                    |
   |<-- 201 { access, refresh } / 400 / 409 --------------------------|
```

### 4.3. Acceso a recurso protegido (`/me`)
```
Cliente                          API
   |--- GET /auth/me -------------->|
   |    Authorization: Bearer <access>
   |                                 |--- JWTAuthentication valida firma y exp
   |<-- 200 { data: user } / 401 ---|
```

### 4.4. Refresh de token
```
Cliente                          API
   |--- POST /auth/token/refresh -->|
   |    { refresh }                 |--- valida refresh token
   |<-- 200 { access } / 401 -------|
```

## 5. Seguridad

- **Algoritmo JWT**: `HS256`, firmado con `SECRET_KEY` de Django (`SIMPLE_JWT.SIGNING_KEY`, config/settings.py:117-121).
- **Vida de los tokens**:
  - Access token: 30 minutos.
  - Refresh token: 1 día.
- **Autenticación por defecto en DRF**: `JWTAuthentication` (`REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`, config/settings.py:95-98).
- **Permiso por defecto en DRF**: `IsAuthenticated` (config/settings.py:99-101) — todo endpoint nuevo requiere auth salvo que se marque explícitamente `AllowAny` (como `login` y `register`).
- **Passwords**: nunca se devuelven en las respuestas (`write_only` en el serializer); se almacenan hasheadas vía `create_user` de Django.
- **Validadores de password**: `AUTH_PASSWORD_VALIDATORS` está configurado en settings (similitud con atributos del usuario, longitud mínima, password común, solo numérica), pero **la API no los aplica** — el registro solo exige 8 caracteres mínimo (ver §3.2). Rigen únicamente para lo que pase por las herramientas de Django que llaman a `validate_password` (por ejemplo `createsuperuser`).
- **CSRF**: `CsrfViewMiddleware` está activo globalmente, pero los endpoints de auth son vistas DRF (`@api_view`) que no dependen de sesión/cookies, por lo que no aplica CSRF a estas llamadas.

## 6. Manejo de errores

Formato de error JSON:API usado por `login`, `register` y `me` (helper `_error()` en [auth_service.py](../../app/users/services/auth_service.py#L8)):
```json
{ "errors": [{ "status": "401", "detail": "Credenciales inválidas" }] }
```

Para errores de validación de `register`, se agrega `source.pointer`:
```json
{
  "errors": [
    { "status": "400", "source": { "pointer": "/data/attributes/email" }, "detail": "Enter a valid email address." }
  ]
}
```

| Código | Endpoints donde aparece | Causa |
|--------|--------------------------|-------|
| 400 | login, register | Body no sigue estructura `{ data: { type, attributes } }`, campos faltantes, o falla de validación del serializer |
| 401 | login, me, token/refresh | Credenciales inválidas / token ausente, inválido o expirado |
| 409 | register | `username` o `email` ya existen |

> Nota: `token/refresh` usa el formato de error nativo de `simplejwt`, no el formato JSON:API del resto de los endpoints (ver [3.3](#33-post-apiv1authtokenrefresh)).

## 7. Configuración relacionada

En [config/settings.py](../../config/settings.py):

```python
AUTH_USER_MODEL = 'users.Users'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
}
```

Middleware relevante (orden real en `MIDDLEWARE`): `SecurityMiddleware` → `SessionMiddleware` → `CommonMiddleware` → `CsrfViewMiddleware` → `AuthenticationMiddleware` → `MessageMiddleware` → `XFrameOptionsMiddleware`. `AuthenticationMiddleware` es el de sesión de Django (usado por el admin); la autenticación de la API pasa por `JWTAuthentication`, no por este middleware.

Versiones instaladas (requirements.txt): `Django==5.0.4`, `djangorestframework==3.16.0`, `djangorestframework-simplejwt==5.5.0`, `drf-spectacular==0.29.0`.

## 8. Notas sobre el estado actual

Funcionalidad relacionada a auth que **no está implementada** hoy (registrado como referencia factual, no como pendiente a resolver):

- No hay endpoint de **logout** ni blacklist de refresh tokens (`rest_framework_simplejwt.token_blacklist` no está en `INSTALLED_APPS`) — un refresh token sigue siendo válido hasta que expira, aunque el usuario "cierre sesión" del lado del cliente.
- No hay **rotación de refresh token** (`ROTATE_REFRESH_TOKENS` no configurado, default `False`).
- No hay **reset/recuperación de password**.
- No hay **verificación de email** al registrarse.
- No hay **rate limiting / throttling** configurado en `REST_FRAMEWORK` para los endpoints de auth.
- El campo `role` no tiene `choices` definidas ni un endpoint para modificarlo; todo usuario registrado por API queda con `role='user'`.
- No hay endpoint para **cambiar password** de un usuario autenticado.
