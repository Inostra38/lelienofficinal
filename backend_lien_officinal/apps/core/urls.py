from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PharmacyViewSet

# Définition du Router
router = DefaultRouter()
router.register(r'pharmacy', PharmacyViewSet, basename='pharmacy')

urlpatterns = [
    path('', include(router.urls)),
]
