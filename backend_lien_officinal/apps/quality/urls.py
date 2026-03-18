from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProcedureViewSet, ProcedureAttachmentViewSet,
    NonConformityViewSet, CorrectiveActionViewSet,
)
from .views_ai import generate_procedure_content, suggest_corrective_actions

router = DefaultRouter()
router.register(r'procedures', ProcedureViewSet, basename='procedure')
router.register(r'attachments', ProcedureAttachmentViewSet, basename='attachment')
router.register(r'nonconformities', NonConformityViewSet, basename='nonconformity')
router.register(r'actions', CorrectiveActionViewSet, basename='corrective-action')

urlpatterns = [
    path('', include(router.urls)),
    path('ai/generate-procedure/', generate_procedure_content, name='ai-generate-procedure'),
    path('ai/suggest-actions/', suggest_corrective_actions, name='ai-suggest-actions'),
]
