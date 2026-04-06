release: cd frontend-lien-officinal && npm install --legacy-peer-deps && npx ng build --configuration production && cd ../backend_lien_officinal && python manage.py migrate --noinput && python manage.py collectstatic --noinput
web: cd backend_lien_officinal && daphne -b 0.0.0.0 -p $PORT backend_lien_officinal.asgi:application
worker: cd backend_lien_officinal && celery -A backend_lien_officinal worker --loglevel=info
