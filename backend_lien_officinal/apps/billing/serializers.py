from rest_framework import serializers

from apps.billing.models import Subscription, Invoice


class SubscriptionSerializer(serializers.ModelSerializer):
    is_access_allowed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'plan', 'status', 'trial_ends_at',
            'current_period_end', 'is_access_allowed',
        ]
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_type',
            'amount_ht', 'tva_rate', 'amount_ttc',
            'issued_at', 'paid_at',
        ]
        read_only_fields = fields


class PromoCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
