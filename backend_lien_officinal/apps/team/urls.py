from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CollaboratorViewSet

# 1. Définition du Router
router = DefaultRouter()
# Route de base : /api/team/ (pour GET, et POST verify-pin)
router.register(r'team', CollaboratorViewSet, basename='team')

# 2. Définition des URLs finales
urlpatterns = [
    path('', include(router.urls)),
]