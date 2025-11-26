# apps/partners/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('ads/inactivity/', views.get_inactivity_ad, name='inactivity-ad'),
]