from rest_framework import serializers

from apps.billing.models import Subscription, Invoice


class SubscriptionSerializer(serializers.ModelSerializer):
    is_access_allowed = serializers.BooleanField(read_only=True)
    # Motif du refus, pour que le frontend formule un message juste plutôt que
    # de le déduire du statut (un TRIALING peut être en cours OU expiré).
    access_denied_reason = serializers.CharField(read_only=True, allow_null=True)
    # Compte à rebours de la grâce d'impayé (null hors de cet état) — alimente
    # le bandeau « mettez à jour votre RIB sous X jours ».
    grace_days_left = serializers.IntegerField(read_only=True, allow_null=True)
    has_stripe_subscription = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'plan', 'status', 'trial_ends_at',
            'current_period_end', 'cancel_at_period_end',
            'has_stripe_subscription', 'is_access_allowed',
            'access_denied_reason', 'grace_days_left',
        ]
        read_only_fields = fields

    def get_has_stripe_subscription(self, obj) -> bool:
        """True dès qu'un abonnement Stripe réel existe (vs simple ébauche)."""
        return bool(obj.stripe_subscription_id)


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
