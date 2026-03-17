from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProcedureViewSet, ProcedureAttachmentViewSet,
    NonConformityViewSet, CorrectiveActionViewSet,
)

router = DefaultRouter()
router.register(r'procedures', ProcedureViewSet, basename='procedure')
router.register(r'attachments', ProcedureAttachmentViewSet, basename='attachment')
router.register(r'nonconformities', NonConformityViewSet, basename='nonconformity')
router.register(r'actions', CorrectiveActionViewSet, basename='corrective-action')

urlpatterns = [
    path('', include(router.urls)),
]
