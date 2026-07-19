release: echo ">>> RELEASE_PHASE migrate+collectstatic" && python backend_lien_officinal/manage.py migrate --noinput && python backend_lien_officinal/manage.py collectstatic --noinput
web: cd backend_lien_officinal && daphne -b 0.0.0.0 -p $PORT backend_lien_officinal.asgi:application
worker: cd backend_lien_officinal && celery -A backend_lien_officinal worker --beat --schedule=/tmp/celerybeat-schedule --loglevel=info --concurrency=2 --max-tasks-per-child=10

# --beat : l'ordonnanceur tourne DANS le worker, pas dans un conteneur dédié.
# Sans lui, CELERY_BEAT_SCHEDULE n'était jamais lu et trois tâches nocturnes
# ne s'exécutaient pas — dont execute_scheduled_deletions, qui porte le droit
# à l'effacement RGPD.
#
# ⚠️ CONTRAINTE : le worker doit rester à UN SEUL conteneur. Chaque conteneur
# embarquant son propre ordonnanceur, en scaler deux dupliquerait chaque tâche
# planifiée. Pour scaler le worker, extraire d'abord beat dans son propre
# process type :
#     beat: cd backend_lien_officinal && celery -A backend_lien_officinal beat --loglevel=info
#
# --schedule dans /tmp : le disque Scalingo est éphémère, on évite d'écrire
# le fichier d'état à la racine de l'application.
