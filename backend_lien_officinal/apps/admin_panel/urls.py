from django.urls import path
from .views import (
    AdminLoginView,
    AdminTotpVerifyView,
    AdminTokenRefreshView,
    AdminLogoutView,
    AdminTotpSetupView,
    AdminTotpSetupConfirmView,
)

urlpatterns = [
    path('auth/login/', AdminLoginView.as_view(), name='admin-login'),
    path('auth/totp-verify/', AdminTotpVerifyView.as_view(), name='admin-totp-verify'),
    path('auth/refresh/', AdminTokenRefreshView.as_view(), name='admin-token-refresh'),
    path('auth/logout/', AdminLogoutView.as_view(), name='admin-logout'),
    path('auth/totp-setup/', AdminTotpSetupView.as_view(), name='admin-totp-setup'),
    path('auth/totp-setup/confirm/', AdminTotpSetupConfirmView.as_view(), name='admin-totp-setup-confirm'),
]
