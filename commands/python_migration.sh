#!/bin/bash

param1=$1

case $param1 in
    "show_migrations")
        python manage.py showmigrations
        ;;
    "build_migration")
        python manage.py makemigrations
        ;;
    "make_migration")
        python manage.py migrate
        ;;
    *)
        echo "Invalid parameter. Please use one of the following: show_migrations, build_migration, make_migration"
        ;;
esac



