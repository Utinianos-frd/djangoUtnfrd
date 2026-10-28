# Type checking (mypy)

Spec de la herramienta de análisis estático instalada en el proyecto — el equivalente a PHPStan en el mundo Python. Tooling de calidad interna, no un requerimiento del documento de Tasker, documentado igual por la misma práctica que el resto de `specs/`.

> Dos tandas: primero instalación y configuración (sin tocar código). Después, a pedido explícito, se tiparon las firmas de los 4 apps completos (modelos, servicios, vistas) — ver sección 5. `python -m mypy app config` corre hoy **sin errores** sobre 83 archivos.

## 1. Qué se instaló

- **mypy** 2.4.0 — el chequeador de tipos está en [requirements.txt](../requirements.txt).
- **django-stubs** 5.0.4 — stubs de Django para que mypy entienda `QuerySet`, campos de modelo, el manager `.objects`, etc. (sin esto, mypy ve a Django como una caja negra). **Importante**: se fijó la versión `5.0.4` a propósito, para que coincida con la versión real de Django del proyecto (`Django==5.0.4`) — la versión más nueva de django-stubs (6.x) tipa una API de Django más reciente y generaba un falso positivo en `CheckConstraint(check=...)` (en Django 5.1+ ese parámetro se renombró a `condition`; en 5.0 sigue siendo `check`, que es lo que usa este proyecto).
- **djangorestframework-stubs** 3.15.1 — ídem para DRF (`Request`, `Response`, `Serializer`, etc.), pineado a una versión compatible con la de django-stubs elegida.

## 2. Configuración

[mypy.ini](../mypy.ini), en la raíz:

```ini
[mypy]
python_version = 3.12
plugins = mypy_django_plugin.main
ignore_missing_imports = True
check_untyped_defs = True
explicit_package_bases = True
mypy_path = .
exclude = (migrations/|staticfiles/)

[mypy.plugins.django-stubs]
django_settings_module = config.settings

[mypy-*.migrations.*]
ignore_errors = True
```

- `explicit_package_bases = True` + `mypy_path = .`: imprescindibles en este proyecto. Las apps (`app/users`, `app/organizations`, etc.) son **namespace packages** (sin `__init__.py` en `app/` ni en cada app — ver decisión original en la spec de organizaciones), y varias tienen un subpaquete `models/` con el mismo nombre. Sin esta opción, mypy no puede distinguir `app.organizations.models` de `app.focus.models` y falla con `Duplicate module named "models"` antes de poder chequear nada.
- `check_untyped_defs = True`: sin type hints en el código (que es la situación actual), mypy igual intenta inferir e infiere lo posible dentro de cada función, en vez de saltearse por completo las funciones sin anotar. Es lo que permitió que ya encontrara los 3 hallazgos de la sección 4 sin que nadie haya escrito un solo `: int` todavía.
- Se excluyen `migrations/` (autogeneradas, no vale la pena tipar ni revisar) y `staticfiles/`.

## 3. Cómo correrlo

```bash
python -m mypy app config
# o: bash commands/dev.sh typecheck
# para un subconjunto: bash commands/dev.sh typecheck app/organizations
```

## 4. Un ajuste de código que sí hizo falta (no es "agregar type hints")

Al correrlo por primera vez, mypy tiraba `"type[Comment]" has no attribute "objects"` y lo mismo para `Pomodoro` — un falso positivo conocido del plugin de django-stubs cuando los modelos viven en un paquete `models/` con varios archivos (en vez de un único `models.py`), donde el plugin a veces no logra inyectar automáticamente el manager `objects` para algunos modelos. El arreglo estándar (recomendado por la propia documentación de django-stubs) es declararlo explícito:

```python
class Comment(models.Model):
    objects: models.Manager['Comment'] = models.Manager()
    ...
```

Se aplicó en [Comment](../app/tasks/models/comment.py) y [Pomodoro](../app/focus/models/pomodoro.py) — las dos únicas instancias de este problema en el proyecto. No cambia ningún comportamiento (`objects` ya existía en tiempo de ejecución; esto solo lo hace visible para el chequeador estático).

## 5. Segunda tanda: type hints en los 4 apps

A pedido explícito, se agregaron type hints a modelos, serializers (solo donde hacía falta — la mayoría son puramente declarativos y no necesitan nada), servicios y vistas de `app/users`, `app/organizations`, `app/tasks` y `app/focus`. Convenciones usadas:

- **Servicios**: `def crear_X(request: Request, organization_id: int, ...) -> tuple[dict[str, Any], int]`. Las funciones que pueden devolver `None, 204` (los `eliminar_*`) usan `tuple[dict[str, Any] | None, int]`.
- **Vistas**: `def vista(request: Request, ...) -> Response`. Cuando una vista combina una rama que borra (devuelve `None`) con otras que devuelven un dict, la variable `data` se anota explícito como `dict[str, Any] | None` antes del `if/elif/else` — si no, mypy infiere el tipo de la primera rama que ve y se queja en las siguientes.
- **`request.user`**: DRF tipa `Request.user` como `Any | AnonymousUser` — no como `Users`, el modelo real de este proyecto — porque en general no sabe si la vista exige autenticación. Como `IsAuthenticated` es el default de `REST_FRAMEWORK` en este proyecto (todo excepto login/register/el seed), se usa `cast(Users, request.user)` en cada función que lo necesita, importando `app.users.models.Users`. Es un patrón que se repite mucho (una vez por función que toca `request.user`), pero es el fix estándar para este caso en proyectos Django+DRF+mypy — la alternativa (una `Request` subclase propia con `user: Users`) es más infraestructura de la que se justifica acá.
- **Funciones que reciben `organization`/`group` que pueden ser `None`** (resueltas por un helper tipo `_get_org_group_project`): se tipan `Organization | None` / `Group | None` en vez de forzar un `assert` en cada call site — es más fiel a lo que de verdad puede pasar, y los helpers (`_org_role`, `_is_group_lead`, etc.) ya toleran `None` sin problema (una query con `group=None` simplemente no matchea nada).

### Los 3 hallazgos del primer run, resueltos (no solo tipados)

1. **`task_service.py` (variable `serializer` reusada con dos tipos distintos)**: se separó en `lead_serializer` y `status_serializer`, una por rama. Cero cambio de comportamiento (confirmado con un smoke test end-to-end antes/después).
2. **`dependency_service.py` (`dependencies` a veces `QuerySet`, a veces `list`)**: se unificó convirtiendo la rama de owner/admin/group lead a `list(...)` también, con la variable anotada `dependencies: list[TaskDependency]`.
3. **`pomodoro_service.py` (`pomodoro.paused_at` podía ser `None` para mypy)**: se agregó `assert pomodoro.paused_at is not None` justo antes de la resta, documentando en el propio código la invariante de negocio (solo se llega ahí con `status == PAUSED`, que es el único momento en que `paused_at` está seteado). Mismo patrón aplicado preventivamente en `focus_session_service.finalizar_sesion`, sobre `completed_at`.

Los tres se verificaron con `manage.py check`, la suite completa de pytest, y smoke tests end-to-end manuales adicionales para `task_service.py` y Modo Foco (las dos áreas sin cobertura de pytest todavía) — no solo con mypy en verde.

## 6. Notas sobre el estado actual

- `python -m mypy app config` da `Success: no issues found in 83 source files` — cero errores en todo el proyecto.
- No está integrado a `commands/dev.sh test` ni corre junto a pytest — es un comando aparte (`typecheck`), a propósito: son herramientas con objetivos distintos (pytest verifica comportamiento, mypy verifica consistencia de tipos) y conviene poder correrlas por separado.
- No hay CI corriendo esto en cada push — mismo estado que pytest (ver [specs/pruebas-unitarias.md](pruebas-unitarias.md)).
- Quedó sin tipar deliberadamente: las migraciones (excluidas por config) y los archivos de `tests/` de `app/organizations` — no se tocaron en esta tanda, aunque mypy no se queja de ellos tampoco al no estar en el path por default (`app config`, no `app/organizations/tests`).
