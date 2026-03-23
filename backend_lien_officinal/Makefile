PYTHON := .venv/bin/python
PIP    := .venv/bin/pip

.PHONY: help run test lint migrate mm shell db-reset

help:
	@echo ""
	@echo "  make run        Lancer le serveur Django (dev)"
	@echo "  make test       Lancer les tests Django"
	@echo "  make lint       Vérifier le style (flake8)"
	@echo "  make migrate    Appliquer les migrations"
	@echo "  make mm         makemigrations"
	@echo "  make shell      Django shell"
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
