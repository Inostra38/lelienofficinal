from django.urls import path, include
from rest_framework.routers import DefaultRouter
# 👇 AJOUTE LinkViewSet ICI
from .views import CategoryViewSet, LinkViewSet 

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)

# 👇 AJOUTE CETTE LIGNE POUR CÂBLER L'API D'AJOUT
router.register(r'links', LinkViewSet, basename='links')

urlpatterns = [
    path('', include(router.urls)),
]