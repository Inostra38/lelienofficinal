from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='categories')
router.register(r'cards', views.ResourceCardViewSet, basename='cards')
router.register(r'items', views.ResourceItemViewSet, basename='items')
router.register(r'catalog/cards', views.CatalogCardViewSet, basename='catalog-cards')

urlpatterns = [
    # Onboarding
    path('categories/init/', views.init_categories, name='categories-init'),

    # Routes spécifiques AVANT le router
    path('cards/create-full/', views.create_full_card, name='create-full-card'),
    path('cards/<int:pk>/assign-category/', views.assign_category_to_card, name='assign-category'),
    path('cards/<int:pk>/toggle-favorite/', views.toggle_favorite, name='toggle-favorite'),
    path('cards/<int:pk>/update-notes/', views.update_notes, name='update-notes'),
    
    # ✅ Router en dernier
    path('', include(router.urls)),
]