#!/bin/bash
# Comandos cortos para el día a día del proyecto. Correr desde adentro del
# contenedor 'web' (terminal del devcontainer, o 'docker compose exec web bash').
#
# Uso: bash commands/dev.sh <comando>
# (o './commands/dev.sh <comando>' si ya tiene permiso de ejecución)

set -e

cmd=$1
shift || true

case "$cmd" in
    run)
        python manage.py runserver 0.0.0.0:8000
        ;;

    migrate)
        python manage.py migrate "$@"
        ;;

    makemigrations)
        python manage.py makemigrations "$@"
        ;;

    showmigrations)
        python manage.py showmigrations "$@"
        ;;

    superuser)
        python manage.py createsuperuser
        ;;

    shell)
        python manage.py shell
        ;;

    check)
        python manage.py check
        ;;

    test)
        python -m pytest "$@"
        ;;

    install)
        pip install -r requirements.txt
        ;;

    seed)
        echo "Pegándole a POST /api/v1/dev/seed (necesita el server corriendo en localhost:8000, ver 'run')..."
        curl -sf -X POST http://localhost:8000/api/v1/dev/seed && echo
        ;;

    help|""|*)
        if [ -n "$cmd" ] && [ "$cmd" != "help" ]; then
            echo "Comando desconocido: '$cmd'"
            echo
        fi
        cat <<EOF
Comandos disponibles (bash commands/dev.sh <comando>):

  run              Levanta el servidor de desarrollo en 0.0.0.0:8000
  migrate          Aplica las migraciones pendientes
  makemigrations   Genera migraciones nuevas a partir de cambios en los modelos
  showmigrations   Lista migraciones y cuáles están aplicadas
  superuser        Crea un superusuario (para /admin/)
  shell            Abre el shell interactivo de Django
  check            Corre las validaciones de Django (manage.py check)
  test             Corre la suite de pytest (acepta args, ej: test app/organizations -v)
  install          Instala/actualiza dependencias de requirements.txt
  seed             Puebla datos de prueba (POST /api/v1/dev/seed, requiere 'run' en otra terminal)
  help             Muestra esta ayuda
EOF
        [ -z "$cmd" ] || [ "$cmd" = "help" ]
        ;;
esac
