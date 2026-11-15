# Seed de datos de prueba

Spec técnico del endpoint de seed, pensado para que el equipo tenga usuarios con contraseña conocida para probar el sistema sin tener que crear datos a mano.

## 1. Resumen

- `POST /api/v1/dev/seed` crea (o reutiliza, si ya existen) una organización de demo con un usuario por cada rol del sistema, a nivel organización y a nivel grupo.
- **Solo existe cuando `DEBUG=True`.** La ruta se registra condicionalmente en [config/urls.py](../config/urls.py): si `DEBUG=False`, el `path()` ni siquiera se agrega a `urlpatterns`, así que la URL devuelve 404 real (no es un chequeo dentro de la vista) en cualquier ambiente que no sea desarrollo local.
- Es **idempotente**: correrlo varias veces no duplica organización, grupo ni memberships (usa `get_or_create`). Las contraseñas sí se reescriben en cada corrida, para garantizar que las credenciales documentadas siempre funcionen aunque alguien las haya cambiado probando el sistema.
- No sigue el formato JSON:API del resto de la API (como `token/refresh`, es una ruta de utilidad, no un recurso de dominio).

## 2. Qué crea

| Entidad | Valor |
|---|---|
| Organización | `Tasker Demo`, con plan **Pro** activo (para que el Modo Foco funcione) |
| Grupos | `Backend` y `Frontend` |
| Proyectos | `API v2`, `Migración a Postgres 16` (Backend); `Rediseño Landing`, `App Mobile` (Frontend) |
| Tareas | 17, repartidas entre `pending`, `in_progress` y `done` (las `done` con `closed_at`), con asignados |
| Dependencias | 8 (FS y FF), coherentes con los estados de las tareas — varias tareas quedan bloqueadas |
| Comentarios | 9, de distintos usuarios |
| Modo Foco | Una sesión terminada de `contributor` (con pomodoros completados/cancelados) y una activa de `grouplead` (con un pomodoro corriendo) |

| Usuario | Password | Rol de organización | Rol de grupo |
|---|---|---|---|
| `owner` | `owner123` | `owner` | — |
| `admin` | `admin123` | `admin` | — |
| `member` | `member123` | `member` | — |
| `grouplead` | `grouplead123` | `member` | `group_lead` (Backend) |
| `contributor` | `contributor123` | `member` | `contributor` (Backend y Frontend) |
| `lucia` | `lucia123` | `member` | `group_lead` (Frontend) |
| `mateo` | `mateo123` | `member` | `contributor` (Frontend) |
| `sofia` | `sofia123` | `member` | `contributor` (Backend) |

Email de cada usuario: `{username}@tasker.test`. `role` del modelo `Users` (campo genérico, no el rol de organización): `'user'` para todos, igual que en el registro normal.

Los 5 primeros cubren los 5 roles del documento de especificación (secciones 3.1 y 3.2). Los otros tres son compañeros de relleno para que el workload y el dashboard tengan contenido. La carga está armada a propósito: `contributor` queda **overloaded** (≥ 5 tareas activas con el umbral por defecto), `grouplead`/`sofia`/`lucia` **busy** y `mateo` **available**.

Idempotencia de los datos de dominio: proyectos y tareas se buscan por nombre/título; asignados, fechas y pomodoros solo se cargan cuando la fila se crea, así que si alguien modificó una tarea de prueba, el seed no la pisa. Si un usuario ya tiene otra sesión de foco activa, no se le crea la del seed.

## 3. Request / Response

**Request**: `POST /api/v1/dev/seed`, sin body, sin autenticación (`AllowAny`).

**Response 200** (credenciales recortadas)
```json
{
  "organization": "Tasker Demo",
  "groups": ["Backend", "Frontend"],
  "summary": { "users": 8, "projects": 4, "tasks": 17, "dependencies": 8, "comments": 9, "focus_sessions": 2 },
  "credentials": [
    { "username": "owner", "password": "owner123", "org_role": "owner", "group_roles": {} },
    { "username": "contributor", "password": "contributor123", "org_role": "member",
      "group_roles": { "Backend": "contributor", "Frontend": "contributor" } }
  ]
}
```

Con cualquiera de esas credenciales se puede loguear normalmente vía `POST /api/v1/auth/login` (ver [login/sistema-logueo.md](login/sistema-logueo.md)).

## 4. Implementación

- [app/organizations/services/seed_service.py](../app/organizations/services/seed_service.py): `run_seed()` — lógica de creación/reutilización.
- [app/organizations/tests/test_seed_service.py](../app/organizations/tests/test_seed_service.py): tests de creación e idempotencia.
- [app/organizations/views/seed_view.py](../app/organizations/views/seed_view.py): vista DRF que expone el servicio.
- Registro condicional de la ruta en [config/urls.py](../config/urls.py), gateado por `settings.DEBUG`.

## 5. Decisiones de diseño

- **Endpoint en vez de management command**: se eligió así explícitamente para que cualquiera del equipo pueda generar los datos de prueba pegándole a la URL (desde Swagger, Postman, etc.) sin necesidad de abrir una terminal dentro del contenedor.
- **Gateado por `DEBUG`, no por autenticación**: como el objetivo es que cualquier compañero lo use sin fricción en su entorno local (donde `DEBUG=True` por default, ver `config/settings.py`), no tiene sentido pedir credenciales para un endpoint cuyo propósito es justamente crear las primeras credenciales. La protección real es que la ruta no exista fuera de desarrollo.
- **Passwords fijas y conocidas**: prioriza la practicidad para pruebas manuales del equipo por sobre la seguridad — aceptable porque el endpoint completo deja de existir en cualquier ambiente con `DEBUG=False`.

## 6. Notas sobre el estado actual

- Todo corre dentro de una transacción: si algo falla, no queda la base a medio poblar.
- No valida `AUTH_PASSWORD_VALIDATORS` al crear los usuarios (usa `set_password` directo) — es un atajo aceptable al ser datos de prueba, no un alta real vía `register`.
- Si en algún momento se agrega un endpoint para "limpiar" datos de prueba (reset/deseed), documentarlo en este mismo spec.
