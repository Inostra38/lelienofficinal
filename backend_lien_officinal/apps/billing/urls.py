from django.urls import path

from apps.billing.views import (
    StripeWebhookView,
    BillingStatusView,
    SetupSubscriptionView,
    ConfirmSubscriptionView,
    SmsPackPaymentIntentView,
    InvoiceListView,
    InvoiceDownloadView,
    ValidatePromoCodeView,
)

app_name = 'billing'

urlpatterns = [
    path('webhook/stripe/',  StripeWebhookView.as_view(),        name='stripe-webhook'),
    path('status/',          BillingStatusView.as_view(),         name='billing-status'),
    path('setup/',           SetupSubscriptionView.as_view(),     name='setup-subscription'),
    path('confirm/',         ConfirmSubscriptionView.as_view(),   name='confirm-subscription'),
    path('sms-pack/intent/', SmsPackPaymentIntentView.as_view(),  name='sms-pack-intent'),
    path('invoices/',        InvoiceListView.as_view(),           name='invoice-list'),
    path('invoices/<int:invoice_id>/download/', InvoiceDownloadView.as_view(), name='invoice-download'),
    path('promo/validate/', ValidatePromoCodeView.as_view(),    name='promo-validate'),
]
