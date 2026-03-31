from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PharmacyViewSet, RegisterView, ProfileSetupView, CompleteOnboardingView,
    ChangePasswordView, ChangeEmailView,
    AccountChangePasswordView, AccountChangeEmailView,
    AccountVerifySecurityAccessView, AccountDeleteView,
    LogoutView, CollabLogoutView,
    VerifyEmailView, ResendVerificationEmailView,
    ConfirmEmailChangeView, CancelEmailChangeView,
)
from .views_sms import SMSTemplateViewSet, SMSLogViewSet, SMSPreviewView, SMSSendView, SMSWebhookView, SMSCreditsView, SMSStatsView

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
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/collab-logout/', CollabLogoutView.as_view(), name='collab-logout'),
    path('auth/verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('auth/resend-verification/', ResendVerificationEmailView.as_view(), name='resend-verification'),
    # Formulaires directs (old_password dans le corps de la requête)
    path('account/change-password/', AccountChangePasswordView.as_view(), name='account-change-password'),
    path('account/change-email/', AccountChangeEmailView.as_view(), name='account-change-email'),
    path('account/confirm-email-change/', ConfirmEmailChangeView.as_view(), name='account-confirm-email-change'),
    path('account/cancel-email-change/', CancelEmailChangeView.as_view(), name='account-cancel-email-change'),
    path('account/verify-security-access/', AccountVerifySecurityAccessView.as_view(), name='account-verify-security-access'),
    path('account/delete/', AccountDeleteView.as_view(), name='account-delete'),
    path('sms/preview/', SMSPreviewView.as_view(), name='sms-preview'),
    path('sms/send/', SMSSendView.as_view(), name='sms-send'),
    path('sms/webhook/<str:token>/', SMSWebhookView.as_view(), name='sms-webhook'),
    path('sms/credits/', SMSCreditsView.as_view(), name='sms-credits'),
    path('sms/stats/', SMSStatsView.as_view(), name='sms-stats'),
    path('', include(router.urls)),
]
