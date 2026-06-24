from django.urls import path
from .views import (
    AdminLoginView,
    AdminTotpVerifyView,
    AdminTokenRefreshView,
    AdminLogoutView,
    AdminTotpSetupView,
    AdminTotpSetupConfirmView,
    AdminChangePasswordView,
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
from .billing_views import (
    AdminSubscriptionListView,
    AdminSubscriptionDetailView,
    AdminSubscriptionActionView,
    AdminPromoCodeListCreateView,
    AdminPromoCodeDetailView,
)

urlpatterns = [
    # Auth
    path('auth/login/', AdminLoginView.as_view(), name='admin-login'),
    path('auth/totp-verify/', AdminTotpVerifyView.as_view(), name='admin-totp-verify'),
    path('auth/refresh/', AdminTokenRefreshView.as_view(), name='admin-token-refresh'),
    path('auth/logout/', AdminLogoutView.as_view(), name='admin-logout'),
    path('auth/totp-setup/', AdminTotpSetupView.as_view(), name='admin-totp-setup'),
    path('auth/totp-setup/confirm/', AdminTotpSetupConfirmView.as_view(), name='admin-totp-setup-confirm'),
    path('auth/change-password/', AdminChangePasswordView.as_view(), name='admin-change-password'),

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

    # Abonnements & facturation
    path('subscriptions/', AdminSubscriptionListView.as_view(), name='admin-subscriptions'),
    path('subscriptions/<int:pharmacy_id>/', AdminSubscriptionDetailView.as_view(), name='admin-subscription-detail'),
    path('subscriptions/<int:pharmacy_id>/action/', AdminSubscriptionActionView.as_view(), name='admin-subscription-action'),
    path('promo-codes/', AdminPromoCodeListCreateView.as_view(), name='admin-promo-codes'),
    path('promo-codes/<int:promo_id>/', AdminPromoCodeDetailView.as_view(), name='admin-promo-code-detail'),
]
