from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='categories')
router.register(r'cards', views.ResourceCardViewSet, basename='cards')
router.register(r'items', views.ResourceItemViewSet, basename='items')
router.register(r'catalog/cards', views.CatalogCardViewSet, basename='catalog-cards')

urlpatterns = [
    # Wizard onboarding
    path('wizard/categories/', views.wizard_categories, name='wizard-categories'),
    path('wizard/resources/', views.wizard_resources, name='wizard-resources'),
    path('wizard/classify/', views.wizard_classify, name='wizard-classify'),
    path('wizard/complete/', views.wizard_complete, name='wizard-complete'),

    # Onboarding legacy
    path('categories/init/', views.init_categories, name='categories-init'),

    # Routes spécifiques AVANT le router
    path('cards/create-full/', views.create_full_card, name='create-full-card'),
    path('cards/<int:pk>/assign-category/', views.assign_category_to_card, name='assign-category'),
    path('cards/<int:pk>/toggle-favorite/', views.toggle_favorite, name='toggle-favorite'),
    path('cards/<int:pk>/toggle-visibility/', views.toggle_visibility, name='toggle-visibility'),
    path('cards/<int:pk>/update-notes/', views.update_notes, name='update-notes'),
    path('cards/<int:pk>/recommend/', views.recommend_card, name='recommend-card'),
    path('items/<int:pk>/recommend/', views.recommend_item, name='recommend-item'),
    
    # ✅ Router en dernier
    path('', include(router.urls)),
]