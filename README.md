# Tasker

Sistema de gestión colaborativa de tareas y proyectos por equipos (UTN FRD — Desarrollo de Software). Backend en Django + Django REST Framework, autenticación JWT, documentación OpenAPI vía drf-spectacular.

Specs funcionales y técnicas del proyecto en [`specs/`](specs/).

## Stack

- Python 3.12 / Django 5.0.4 / Django REST Framework 3.16
- PostgreSQL 15
- JWT (`djangorestframework-simplejwt`)
- Docker + Docker Compose
- Nginx (solo perfil `prod`)

## Requisitos previos

- [Docker](https://docs.docker.com/get-docker/) y Docker Compose (v2, el que viene integrado como `docker compose`).
- Opcional pero recomendado: [VS Code](https://code.visualstudio.com/) con la extensión **Dev Containers**, ya que el repo trae configuración en [`.devcontainer/`](.devcontainer/).

No hace falta tener Python ni PostgreSQL instalados en el host: todo corre dentro de los contenedores.

## 1. Clonar el repo

```bash
git clone https://github.com/Utinianos-frd/djangoUtnfrd.git
cd djangoUtnfrd
```

## 2. Variables de entorno

Copiar el archivo de ejemplo y completarlo:

```bash
cp .env.example .env
```

```env
POSTGRES_USER=tasker
POSTGRES_PASSWORD=tasker
POSTGRES_DB=tasker
```

`.env` está en `.gitignore`: cada integrante define sus propios valores (no importa cuáles mientras `docker-compose.yml` y la app los lean de ahí).

## 3. Levantar el proyecto

Hay dos formas equivalentes. Las dos usan `docker-compose.yml` + `docker-compose.override.yml` (Docker Compose lo mergea automáticamente), que en modo desarrollo deja el contenedor `web` corriendo en espera (`sleep infinity`) en vez de arrancar el servidor solo, para poder ejecutar comandos de Django a mano desde la terminal integrada.

### Opción A — VS Code Dev Containers (recomendado)

1. Abrir la carpeta del proyecto en VS Code.
2. "Reopen in Container" (paleta de comandos → *Dev Containers: Reopen in Container*).
3. Esperar a que termine el build (instala dependencias de `requirements.txt` y herramientas del `Dockerfile`).
4. Se abre una terminal integrada ya **dentro** del contenedor `web`, en `/workspace`. Continuar con el paso 4 de este README (migraciones).

### Opción B — Docker Compose directo (sin VS Code)

```bash
docker compose up -d
```

Esto levanta `web` (Django) y `postgres`. Como el contenedor `web` queda en espera, hay que entrar a él para correr comandos:

```bash
docker compose exec web bash
```

A partir de acá los pasos son los mismos que en la Opción A (ya estás dentro del contenedor).

> **Atajo**: `commands/dev.sh` agrupa los comandos de Django más usados (migrar, levantar el server, seed, etc.) para no tener que acordarse cada uno. Corré `bash commands/dev.sh help` dentro del contenedor para ver la lista completa. Abajo están los comandos equivalentes por si prefieren usar `manage.py` directo.

## 4. Migraciones

Dentro del contenedor `web`:

```bash
python manage.py migrate
# o: bash commands/dev.sh migrate
```

## 5. Crear un superusuario (opcional, para /admin/)

```bash
python manage.py createsuperuser
# o: bash commands/dev.sh superuser
```

## 6. Levantar el servidor de desarrollo

```bash
python manage.py runserver 0.0.0.0:8000
# o: bash commands/dev.sh run
```

La app queda disponible en [http://localhost:8000](http://localhost:8000) (el puerto 8000 ya está mapeado al host por `docker-compose.override.yml`). El puerto 5432 de Postgres también queda expuesto al host por si querés conectarte con un cliente de DB externo.

## 7. Datos de prueba (seed)

Para no tener que crear usuarios a mano, con el servidor corriendo (y las migraciones aplicadas) pegale una vez a:

```bash
curl -X POST http://localhost:8000/api/v1/dev/seed
# o (en otra terminal dentro del contenedor, con 'run' corriendo): bash commands/dev.sh seed
```

o desde el Swagger (`/api/v1/docs/`, tag **Dev**). Esto crea una organización de demo (`Tasker Demo`) con un usuario por cada rol del sistema, todos con password conocida:

| Usuario | Password | Rol de organización | Rol de grupo |
|---|---|---|---|
| `owner` | `owner123` | `owner` | — |
| `admin` | `admin123` | `admin` | — |
| `member` | `member123` | `member` | — |
| `grouplead` | `grouplead123` | `member` | `group_lead` (grupo Backend) |
| `contributor` | `contributor123` | `member` | `contributor` (grupo Backend) |

Logueate con cualquiera de estos vía `POST /api/v1/auth/login`. Es seguro correrlo varias veces (no duplica nada). Esta ruta **solo existe si `DEBUG=True`** (así viene por default en este repo) — detalle completo en [specs/seed-de-datos-de-prueba.md](specs/seed-de-datos-de-prueba.md).

## Documentación de la API

Con el servidor corriendo:

- Swagger UI: `http://localhost:8000/api/v1/docs/`
- Redoc: `http://localhost:8000/api/v1/redoc/`
- Schema OpenAPI crudo: `http://localhost:8000/api/v1/schema/`

Todos los endpoints de la API responden en formato [JSON:API](https://jsonapi.org/) (ver [specs/login/sistema-logueo.md](specs/login/sistema-logueo.md) para el detalle de auth).

## Estructura del proyecto

```
app/
  users/          # autenticación (login, registro, JWT) — ver specs/login/sistema-logueo.md
  organizations/  # Organización, Membership, Group, GroupMembership, Workload — ver specs/organizaciones-y-roles.md, specs/grupos_y_roles/grupos-y-roles.md y specs/workload.md
  tasks/          # Proyecto y Tarea (ABM básico) — ver specs/proyectos.md y specs/tareas.md. Dependencias y comentarios: todavía no implementados
config/           # settings, urls, wsgi/asgi del proyecto Django
specs/            # specs funcionales y técnicas de cada módulo
commands/         # atajos de shell (ver "Atajo" en la sección de setup) — bash commands/dev.sh help
```

## Perfil de producción (nginx)

El `docker-compose.yml` incluye un servicio `nginx` detrás del perfil `prod`, que sirve estáticos y hace de proxy a `web`:

```bash
docker compose --profile prod up -d
```

Este flujo no está pensado para desarrollo local día a día — es para probar la topología de producción (nginx + gunicorn) de forma local.

## Troubleshooting

- **El contenedor `web` figura como "unhealthy"**: el healthcheck de `docker-compose.yml` pega contra `http://localhost:8000/health/`, un endpoint que todavía no está implementado en la app. Es un falso positivo conocido — no afecta que el servidor responda en `/`; se puede ignorar mientras no se agregue ese endpoint.
- **Error de conexión a Postgres**: verificar que `.env` tenga `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` completos y que coincidan con lo que Django lee en `config/settings.py`.
- **Puerto 8000 o 5432 ocupado en el host**: liberar el puerto o cambiar el mapeo en `docker-compose.override.yml`.
