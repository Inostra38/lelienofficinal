from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProcedureViewSet, ProcedureAttachmentViewSet, ProcedureImageViewSet,
    NonConformityViewSet, CorrectiveActionViewSet,
    ProcedureGroupViewSet, ProcedureCategoryViewSet,
    ProcedureNotificationViewSet,
)
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
]
