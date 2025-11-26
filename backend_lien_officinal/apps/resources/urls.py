from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views # Importe toutes les vues (pour accéder à views.assign_category_to_card)

# 1. Définition du Router (pour les ViewSets)
router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='categories')
router.register(r'cards', views.ResourceCardViewSet, basename='cards')
router.register(r'items', views.ResourceItemViewSet, basename='items')
router.register(r'catalog/cards', views.CatalogCardViewSet, basename='catalog-cards')

# 2. Définition des URLs spécifiques (pour les fonctions @api_view)
urlpatterns = [
    # Routes des ViewSets
    path('', include(router.urls)),
    
    # 🚨 FIX CRITIQUE : AJOUT DE LA ROUTE MANUELLE 🚨
    # Le ViewSet ne gère pas les actions qui ne sont pas standard (POST/GET/PATCH).
    path('cards/<int:pk>/assign-category/', views.assign_category_to_card, name='assign-category'),
]