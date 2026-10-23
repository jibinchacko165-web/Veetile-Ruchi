web: gunicorn veetile_ruchi_project.wsgi:application --config gunicorn.conf.py
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
