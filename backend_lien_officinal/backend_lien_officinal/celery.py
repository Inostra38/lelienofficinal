import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_lien_officinal.settings')

app = Celery('backend_lien_officinal')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
