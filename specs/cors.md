# CORS

Spec técnico de la configuración de CORS (Cross-Origin Resource Sharing) de la API, necesaria para que un frontend servido en otro origen (ej. Angular en `localhost:4200`) pueda consumirla desde el navegador.

## 1. Resumen

- Librería: [`django-cors-headers`](https://github.com/adamchainz/django-cors-headers) 4.9.0.
- Por default permite **únicamente** `http://localhost:4200` (el dev server típico de Angular). Configurable por entorno vía la variable de entorno `CORS_ALLOWED_ORIGINS`.
- Sin esta configuración, un navegador corriendo el frontend en `http://localhost:4200` bloquea las respuestas de `http://localhost:8000` por política de mismo origen, aunque la API responda bien — el fetch/XHR falla del lado del browser antes de llegar al código del frontend.

## 2. Configuración

[config/settings.py](../config/settings.py):

```python
INSTALLED_APPS = [
    ...
    'corsheaders',
    ...
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    ...
]

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:4200').split(',')
    if origin.strip()
]
```

- `CorsMiddleware` va **antes** de `CommonMiddleware`, como exige la librería (necesita poder agregar headers a la respuesta antes de que `CommonMiddleware` la procese).
- `CORS_ALLOWED_ORIGINS` lee de la variable de entorno `CORS_ALLOWED_ORIGINS`, separada por comas, con `http://localhost:4200` como default si no está seteada. Agregada a [.env.example](../.env.example).
- No se usa `CORS_ALLOW_ALL_ORIGINS` (que habilitaría cualquier origen): se optó por un allowlist explícito.
- No se configuró `CORS_ALLOW_CREDENTIALS`: la autenticación es JWT por header `Authorization`, no por cookies, así que no hace falta que el navegador mande/reciba cookies cross-origin.

## 3. Cómo agregar otro origen (ej. un deploy de staging)

En `.env`:
```env
CORS_ALLOWED_ORIGINS=http://localhost:4200,https://tasker-staging.vercel.app
```

## 4. Notas sobre el estado actual

- Solo cubre el origen del frontend de desarrollo. Falta definir los orígenes de producción/staging cuando existan.
- No se tocó `CSRF_TRUSTED_ORIGINS` — no hace falta mientras la API no dependa de sesión/cookies para las rutas que consume el frontend (ver [sistema-logueo.md, sección 5](sistema-logueo.md#5-seguridad) sobre por qué CSRF no aplica a los endpoints de auth actuales).
