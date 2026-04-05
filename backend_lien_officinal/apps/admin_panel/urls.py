from django.urls import path
from .views import (
    AdminLoginView,
    AdminTotpVerifyView,
    AdminTokenRefreshView,
    AdminLogoutView,
    AdminTotpSetupView,
    AdminTotpSetupConfirmView,
    ListCreateResourceView,
    ResourceDetailView,
    ResourceItemCreateView,
    ResourceItemDeleteView,
    ListRecommendationsView,
    ApproveCardView,
    ApproveItemView,
    RejectRecommendationView,
    ListOfficialCardsView,
)

urlpatterns = [
    # Auth
    path('auth/login/', AdminLoginView.as_view(), name='admin-login'),
    path('auth/totp-verify/', AdminTotpVerifyView.as_view(), name='admin-totp-verify'),
    path('auth/refresh/', AdminTokenRefreshView.as_view(), name='admin-token-refresh'),
    path('auth/logout/', AdminLogoutView.as_view(), name='admin-logout'),
    path('auth/totp-setup/', AdminTotpSetupView.as_view(), name='admin-totp-setup'),
    path('auth/totp-setup/confirm/', AdminTotpSetupConfirmView.as_view(), name='admin-totp-setup-confirm'),

    # Ressources
    path('resources/', ListCreateResourceView.as_view(), name='admin-resources'),
    path('resources/<int:card_id>/', ResourceDetailView.as_view(), name='admin-resource-detail'),
    path('resources/<int:card_id>/items/', ResourceItemCreateView.as_view(), name='admin-resource-items'),
    path('resources/items/<int:item_id>/', ResourceItemDeleteView.as_view(), name='admin-resource-item-delete'),

    # Recommandations communautaires
    path('recommendations/', ListRecommendationsView.as_view(), name='admin-recommendations'),
    path('recommendations/card/<int:card_id>/approve/', ApproveCardView.as_view(), name='admin-approve-card'),
    path('recommendations/item/<int:item_id>/approve/', ApproveItemView.as_view(), name='admin-approve-item'),
    path('recommendations/reject/', RejectRecommendationView.as_view(), name='admin-reject'),
    path('recommendations/official-cards/', ListOfficialCardsView.as_view(), name='admin-official-cards'),
]
