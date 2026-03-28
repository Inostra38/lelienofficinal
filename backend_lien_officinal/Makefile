PYTHON  := .venv/bin/python
PIP     := .venv/bin/pip
CELERY  := .venv/bin/celery

.PHONY: help run test lint migrate mm shell celery-worker celery-beat celery-all seed-sms

help:
	@echo ""
	@echo "  make run           Lancer le serveur Django (dev)"
	@echo "  make test          Lancer les tests Django"
	@echo "  make lint          Vérifier le style (flake8)"
	@echo "  make migrate       Appliquer les migrations"
	@echo "  make mm            makemigrations"
	@echo "  make shell         Django shell"
	@echo "  make celery-worker Lancer le worker Celery (envoi SMS async)"
	@echo "  make celery-beat   Lancer le scheduler Celery (cleanup TTL 30j)"
	@echo "  make seed-sms      Générer des logs SMS fictifs (dev)"
	@echo ""

run:
	$(PYTHON) manage.py runserver

test:
	DB_NAME= $(PYTHON) manage.py test apps --verbosity=2

lint:
	$(PYTHON) -m flake8 apps/ --max-line-length=120 --exclude=migrations

migrate:
	$(PYTHON) manage.py migrate

mm:
	$(PYTHON) manage.py makemigrations

shell:
	$(PYTHON) manage.py shell

celery-worker:
	$(CELERY) -A backend_lien_officinal worker --loglevel=info

celery-beat:
	$(CELERY) -A backend_lien_officinal beat --loglevel=info

seed-sms:
	$(PYTHON) manage.py seed_sms_logs --count 20
