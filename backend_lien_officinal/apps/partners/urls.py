# apps/partners/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('http://127.0.0.1:8000/api/ads/inactivity/', views.get_inactivity_ad, name='inactivity-ad'),
]