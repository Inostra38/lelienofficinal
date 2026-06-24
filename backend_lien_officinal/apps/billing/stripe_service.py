import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:

    # ------------------------------------------------------------------ #
    # Customer                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_customer(pharmacy) -> str:
        """Crée un Customer Stripe pour une pharmacie. Retourne le stripe_customer_id."""
        customer = stripe.Customer.create(
            name=pharmacy.nom_officine,
            email=pharmacy.email,
            metadata={'pharmacy_id': str(pharmacy.id)},
        )
        return customer.id

    # ------------------------------------------------------------------ #
    # Subscription                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_subscription(
        stripe_customer_id: str,
        plan: str,
        trial_days: int = 30,
    ) -> stripe.Subscription:
        """
        Crée un abonnement Stripe.
        plan: 'small' | 'large'
        trial_days : 30 par défaut, augmenté si code promo appliqué.
        """
        price_id = (
            settings.STRIPE_PRICE_SMALL
            if plan == 'small'
            else settings.STRIPE_PRICE_LARGE
        )
        return stripe.Subscription.create(
            customer=stripe_customer_id,
            items=[{'price': price_id}],
            trial_period_days=trial_days,
            payment_settings={'payment_method_types': ['sepa_debit']},
            expand=['latest_invoice.payment_intent'],
        )

    @staticmethod
    def update_subscription_plan(stripe_subscription_id: str, new_plan: str) -> stripe.Subscription:
        """Bascule le plan small ↔ large sans prorata, au prochain cycle."""
        price_id = (
            settings.STRIPE_PRICE_SMALL
            if new_plan == 'small'
            else settings.STRIPE_PRICE_LARGE
        )
        subscription = stripe.Subscription.retrieve(stripe_subscription_id)
        return stripe.Subscription.modify(
            stripe_subscription_id,
            items=[{
                'id': subscription['items']['data'][0]['id'],
                'price': price_id,
            }],
            proration_behavior='none',
        )

    @staticmethod
    def cancel_subscription(stripe_subscription_id: str) -> stripe.Subscription:
        """Résilie l'abonnement en fin de période courante."""
        return stripe.Subscription.modify(
            stripe_subscription_id,
            cancel_at_period_end=True,
        )

    # ------------------------------------------------------------------ #
    # SMS Pack — Payment Intent                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_sms_payment_intent(amount_cents: int, pharmacy) -> stripe.PaymentIntent:
        """
        Crée un PaymentIntent CB pour l'achat d'un pack SMS.
        amount_cents: 900 | 2200 | 3900
        """
        return stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='eur',
            payment_method_types=['card'],
            metadata={
                'pharmacy_id': str(pharmacy.id),
                'type': 'sms_pack',
            },
        )

    # ------------------------------------------------------------------ #
    # Webhook verification                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
