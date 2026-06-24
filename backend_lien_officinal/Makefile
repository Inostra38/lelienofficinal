PYTHON  := .venv/bin/python
PIP     := .venv/bin/pip
CELERY  := .venv/bin/celery

.PHONY: help run test lint migrate mm shell celery-worker celery-beat celery-all seed-sms

TESTS := \
  apps.planning.tests.test_calculator apps.planning.tests.test_models \
  apps.planning.tests.test_paye_analytics apps.planning.tests.test_paye_analytics_octobre \
  apps.planning.tests.test_paye_analytics_feries apps.planning.tests.test_paye_analytics_tns \
  apps.planning.tests.test_paye_analytics_cache apps.planning.tests.test_paye_analytics_edge \
  apps.planning.tests.test_performance apps.planning.tests.test_utils \
  apps.planning.tests.test_views_absences apps.planning.tests.test_views_security \
  apps.planning.tests.test_views_shifts apps.planning.tests.test_views_templates \
  apps.quality.tests.test_nc apps.quality.tests.test_procedures \
  apps.quality.tests.test_notifications \
  apps.core.tests.test_sms apps.core.tests.test_auth \
  apps.team.tests.test_models apps.team.tests.test_views \
  apps.resources.tests.test_models apps.admin_panel.tests.test_auth \
  apps.billing.tests.test_models apps.billing.tests.test_promo \
  apps.billing.tests.test_pdf apps.billing.tests.test_webhook \
  apps.billing.tests.test_api apps.billing.tests.test_tasks \
  tests.test_isolation

help:
	@echo ""
	@echo "  make run           Lancer le serveur Django (dev)"
	@echo "  make test          Lancer tous les tests Django"
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
	$(PYTHON) manage.py test $(TESTS) --settings=backend_lien_officinal.settings_test

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
