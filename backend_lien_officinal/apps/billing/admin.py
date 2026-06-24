from django.contrib import admin

from .models import Subscription, Invoice, SmsCreditTransaction, PromoCode, PromoRedemption


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('pharmacy', 'plan', 'status', 'trial_ends_at', 'current_period_end', 'updated_at')
    list_filter = ('plan', 'status')
    search_fields = ('pharmacy__nom_officine', 'pharmacy__email', 'stripe_customer_id', 'stripe_subscription_id')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'pharmacy', 'invoice_type', 'amount_ttc', 'issued_at', 'paid_at')
    list_filter = ('invoice_type',)
    search_fields = ('invoice_number', 'pharmacy__nom_officine', 'stripe_invoice_id')


@admin.register(SmsCreditTransaction)
class SmsCreditTransactionAdmin(admin.ModelAdmin):
    list_display = ('pharmacy', 'delta', 'reason', 'note', 'created_at')
    list_filter = ('reason',)
    search_fields = ('pharmacy__nom_officine', 'note')


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'months_free', 'is_active', 'current_uses', 'max_uses', 'expires_at', 'note')
    list_editable = ('is_active',)
    search_fields = ('code', 'note')
    list_filter = ('is_active',)
    readonly_fields = ('current_uses', 'created_at', 'updated_at')


@admin.register(PromoRedemption)
class PromoRedemptionAdmin(admin.ModelAdmin):
    list_display = ('pharmacy', 'promo_code', 'redeemed_at')
    search_fields = ('pharmacy__nom_officine', 'promo_code__code')
    readonly_fields = ('pharmacy', 'promo_code', 'redeemed_at')
