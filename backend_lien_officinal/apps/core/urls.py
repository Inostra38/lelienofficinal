from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PharmacyViewSet, RegisterView, ProfileSetupView, CompleteOnboardingView,
    ChangePasswordView, ChangeEmailView,
    AccountChangePasswordView, AccountChangeEmailView,
    AccountVerifySecurityAccessView,
)
from .views_sms import SMSTemplateViewSet, SMSLogViewSet, SMSPreviewView, SMSSendView

router = DefaultRouter()
router.register(r'pharmacy', PharmacyViewSet, basename='pharmacy')
router.register(r'sms/templates', SMSTemplateViewSet, basename='sms-template')
router.register(r'sms/logs', SMSLogViewSet, basename='sms-log')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/profile/setup/', ProfileSetupView.as_view(), name='profile-setup'),
    path('auth/onboarding/complete/', CompleteOnboardingView.as_view(), name='onboarding-complete'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('auth/change-email/', ChangeEmailView.as_view(), name='change-email'),
    # Formulaires directs (old_password dans le corps de la requête)
    path('account/change-password/', AccountChangePasswordView.as_view(), name='account-change-password'),
    path('account/change-email/', AccountChangeEmailView.as_view(), name='account-change-email'),
    path('account/verify-security-access/', AccountVerifySecurityAccessView.as_view(), name='account-verify-security-access'),
    path('sms/preview/', SMSPreviewView.as_view(), name='sms-preview'),
    path('sms/send/', SMSSendView.as_view(), name='sms-send'),
    path('', include(router.urls)),
]
