from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PharmacyViewSet, RegisterView, ProfileSetupView, CompleteOnboardingView

router = DefaultRouter()
router.register(r'pharmacy', PharmacyViewSet, basename='pharmacy')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/profile/setup/', ProfileSetupView.as_view(), name='profile-setup'),
    path('auth/onboarding/complete/', CompleteOnboardingView.as_view(), name='onboarding-complete'),
    path('', include(router.urls)),
]
