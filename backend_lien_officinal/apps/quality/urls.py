from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProcedureViewSet, ProcedureAttachmentViewSet, ProcedureImageViewSet,
    NonConformityViewSet, CorrectiveActionViewSet,
    ProcedureGroupViewSet, ProcedureCategoryViewSet,
    ProcedureNotificationViewSet,
)
from .views_ai import generate_procedure_content, suggest_corrective_actions, refactor_text

router = DefaultRouter()
router.register(r'categories', ProcedureCategoryViewSet, basename='procedure-category')
router.register(r'groups', ProcedureGroupViewSet, basename='procedure-group')
router.register(r'procedures', ProcedureViewSet, basename='procedure')
router.register(r'images', ProcedureImageViewSet, basename='image')
router.register(r'attachments', ProcedureAttachmentViewSet, basename='attachment')
router.register(r'nonconformities', NonConformityViewSet, basename='nonconformity')
router.register(r'actions', CorrectiveActionViewSet, basename='corrective-action')
router.register(r'notifications', ProcedureNotificationViewSet, basename='procedure-notification')

urlpatterns = [
    path('', include(router.urls)),
    path('ai/generate-procedure/', generate_procedure_content, name='ai-generate-procedure'),
    path('ai/suggest-actions/', suggest_corrective_actions, name='ai-suggest-actions'),
    path('ai/refactor-text/', refactor_text, name='ai-refactor-text'),
]
