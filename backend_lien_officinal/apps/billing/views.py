import json
import logging
from datetime import datetime, timezone as dt_timezone

import stripe
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from rest_framework import status as drf_status

from apps.billing.models import Subscription, Invoice, PromoCode, PromoRedemption
from apps.billing.serializers import SubscriptionSerializer, InvoiceSerializer
from apps.billing.stripe_service import StripeService
from apps.billing.tasks import (
    generate_subscription_invoice,
    generate_sms_receipt,
    credit_sms_balance,
)

logger = logging.getLogger(__name__)


class PromoValidateThrottle(UserRateThrottle):
    """Anti brute-force / énumération des codes promo (rate dans settings)."""
    scope = 'promo_validate'


def _invoice_subscription_id(stripe_invoice: dict):
    """ID de l'abonnement d'une facture, compatible toutes versions d'API Stripe.

    Avant 2025 : invoice['subscription']. Depuis (API 2025+/dahlia) : déplacé dans
    invoice['parent']['subscription_details']['subscription'].
    """
    sid = stripe_invoice.get('subscription')
    if sid:
        return sid
    parent = stripe_invoice.get('parent') or {}
    return (parent.get('subscription_details') or {}).get('subscription')


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    """
    Endpoint Stripe webhook.
    Stripe signe chaque requête — on vérifie la signature avant tout traitement.
    """

    def post(self, request, *args, **kwargs):
        payload    = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

        try:
            StripeService.construct_webhook_event(payload, sig_header)  # vérifie la signature
        except stripe.SignatureVerificationError:
            logger.warning('Stripe webhook: signature invalide')
            return HttpResponse(status=400)
        except Exception as exc:
            logger.error('Stripe webhook: erreur construction event — %s', exc)
            return HttpResponse(status=400)

        # stripe v15 : les objets ressources n'exposent pas .get(). On retravaille
        # sur le JSON brut (déjà authentifié par la vérif de signature) en dicts natifs.
        event = json.loads(payload)

        handler = self._get_handler(event['type'])
        if handler:
            try:
                handler(event['data']['object'])
            except Exception as exc:
                logger.exception('Stripe webhook: erreur handler %s — %s', event['type'], exc)
                return HttpResponse(status=500)

        return HttpResponse(status=200)

    def _get_handler(self, event_type: str):
        return {
            'invoice.paid':                          self._handle_invoice_paid,
            'invoice.payment_failed':                self._handle_invoice_payment_failed,
            'customer.subscription.updated':         self._handle_subscription_updated,
            'customer.subscription.deleted':         self._handle_subscription_deleted,
            'customer.subscription.trial_will_end':  self._handle_trial_will_end,
            'payment_intent.succeeded':              self._handle_payment_intent_succeeded,
        }.get(event_type)

    # ------------------------------------------------------------------ #
    # Handlers                                                             #
    # ------------------------------------------------------------------ #

    def _handle_invoice_paid(self, stripe_invoice):
        """Abonnement payé → status active + génération facture WeasyPrint."""
        stripe_sub_id = _invoice_subscription_id(stripe_invoice)
        if not stripe_sub_id:
            return

        # Factures à 0 € (essai / proration) : pas de facture client émise.
        if not stripe_invoice.get('amount_paid'):
            return

        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
        except Subscription.DoesNotExist:
            logger.warning('invoice.paid: subscription introuvable %s', stripe_sub_id)
            return

        # Q05 : capturer la période FACTURÉE (start ET end) depuis la ligne
        # Stripe. Avant, seul 'end' était lu et la facture PDF affichait
        # period_start == period_end (les deux = current_period_end).
        period = stripe_invoice['lines']['data'][0]['period']
        period_start_ts = period.get('start')
        period_end_ts = period.get('end')

        sub.status = Subscription.Status.ACTIVE
        sub.current_period_end = datetime.fromtimestamp(period_end_ts, tz=dt_timezone.utc)
        # Impayé régularisé : on réarme le délai de grâce pour un éventuel
        # échec futur, sinon le suivant couperait l'accès immédiatement.
        sub.past_due_since = None
        sub.suspended_at = None
        sub.save(update_fields=[
            'status', 'current_period_end', 'past_due_since', 'suspended_at', 'updated_at',
        ])

        # Génération facture WeasyPrint en tâche asynchrone
        generate_subscription_invoice.delay(
            pharmacy_id=sub.pharmacy_id,
            stripe_invoice_id=stripe_invoice['id'],
            amount_cents=stripe_invoice['amount_paid'],
            period_start_ts=period_start_ts,
            period_end_ts=period_end_ts,
        )

    def _handle_invoice_payment_failed(self, stripe_invoice):
        """Paiement échoué → status past_due + suspension programmée J+7 via Celery."""
        stripe_sub_id = _invoice_subscription_id(stripe_invoice)
        if not stripe_sub_id:
            return

        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
        except Subscription.DoesNotExist:
            return

        sub.status = Subscription.Status.PAST_DUE
        # Origine du délai de grâce de 7 jours. Ne pas réarmer si l'on est déjà
        # en impayé : Stripe réémet l'événement à chaque tentative échouée, et
        # le délai doit courir depuis le PREMIER échec.
        if sub.past_due_since is None:
            sub.past_due_since = datetime.now(dt_timezone.utc)
        sub.save(update_fields=['status', 'past_due_since', 'updated_at'])

        # Email de relance immédiat
        from apps.billing.tasks import schedule_suspension, send_payment_failed_email
        send_payment_failed_email.delay(sub.pharmacy_id)

        # Suspension programmée à J+7 (voir tâche Celery)
        schedule_suspension.apply_async(
            args=[sub.id],
            countdown=7 * 24 * 3600,  # 7 jours
        )

    def _handle_subscription_updated(self, stripe_sub):
        """Plan ou status mis à jour côté Stripe."""
        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub['id'])
        except Subscription.DoesNotExist:
            return

        stripe_status = stripe_sub.get('status', '')
        status_map = {
            'trialing':   Subscription.Status.TRIALING,
            'active':     Subscription.Status.ACTIVE,
            'past_due':   Subscription.Status.PAST_DUE,
            'canceled':   Subscription.Status.CANCELED,
            'unpaid':     Subscription.Status.PAST_DUE,
        }
        fields = []
        if stripe_status in status_map:
            sub.status = status_map[stripe_status]
            fields.append('status')
            # Miroir de _handle_invoice_payment_failed : le délai de grâce doit
            # rester cohérent quelle que soit la voie par laquelle Stripe nous
            # annonce l'impayé ou sa régularisation.
            if sub.status == Subscription.Status.PAST_DUE:
                if sub.past_due_since is None:
                    sub.past_due_since = datetime.now(dt_timezone.utc)
                    fields.append('past_due_since')
            elif sub.status in (Subscription.Status.ACTIVE, Subscription.Status.TRIALING):
                if sub.past_due_since is not None or sub.suspended_at is not None:
                    sub.past_due_since = None
                    sub.suspended_at = None
                    fields.extend(['past_due_since', 'suspended_at'])
        if 'cancel_at_period_end' in stripe_sub:
            sub.cancel_at_period_end = bool(stripe_sub['cancel_at_period_end'])
            fields.append('cancel_at_period_end')
        if fields:
            fields.append('updated_at')
            sub.save(update_fields=fields)

    def _handle_subscription_deleted(self, stripe_sub):
        """Abonnement résilié → status canceled.

        Si une suppression de compte est programmée (résiliation demandée par le
        titulaire), on l'exécute immédiatement à la fin de période.
        """
        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub['id'])
        except Subscription.DoesNotExist:
            return

        sub.status = Subscription.Status.CANCELED
        sub.save(update_fields=['status', 'updated_at'])

        pharmacy = sub.pharmacy
        if pharmacy.deletion_scheduled_for and not pharmacy.anonymized_at:
            from apps.core.tasks import execute_account_deletion_task
            execute_account_deletion_task.delay(pharmacy.id)

    def _handle_trial_will_end(self, stripe_sub):
        """Trial se termine dans 3 jours (Stripe envoie cet event à J-3)."""
        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_sub['id'])
        except Subscription.DoesNotExist:
            return

        from apps.billing.tasks import send_trial_ending_email
        send_trial_ending_email.delay(sub.pharmacy_id)

    def _handle_payment_intent_succeeded(self, payment_intent):
        """Pack SMS acheté → crédit solde + reçu WeasyPrint."""
        metadata = payment_intent.get('metadata', {})
        if metadata.get('type') != 'sms_pack':
            return

        pharmacy_id = metadata.get('pharmacy_id')
        if not pharmacy_id:
            return

        amount_cents = payment_intent['amount']
        # Mapping montant → nombre de SMS
        sms_map = {900: 100, 2200: 250, 3900: 500}
        sms_quantity = sms_map.get(amount_cents, 0)

        if sms_quantity:
            credit_sms_balance.delay(
                pharmacy_id=int(pharmacy_id),
                quantity=sms_quantity,
                payment_intent_id=payment_intent['id'],
                amount_cents=amount_cents,
            )


# ── API (Angular) ─────────────────────────────────────────────────────────────
# Note : le user authentifié EST la pharmacie (core.Pharmacy = AbstractBaseUser),
# d'où `request.user` partout (et non `request.user.pharmacy`).


class BillingStatusView(APIView):
    """Retourne le statut abonnement + crédits SMS de la pharmacie."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacy = request.user
        sub = Subscription.objects.filter(pharmacy=pharmacy).first()
        sub_data = SubscriptionSerializer(sub).data if sub else None

        from apps.billing.promo_service import get_pharmacy_promo
        promo = get_pharmacy_promo(pharmacy)
        promo_data = {
            'code':        promo.code,
            'months_free': promo.months_free,
        } if promo else None

        return Response({
            'subscription': sub_data,
            # Solde porté par Pharmacy.sms_credits (pas de modèle SmsCredit)
            'sms_credit': {'balance': pharmacy.sms_credits},
            'promo':      promo_data,
        })


class SetupSubscriptionView(APIView):
    """
    Crée le Customer Stripe si inexistant + un SetupIntent SEPA.
    Retourne le client_secret pour que Angular finalise le setup SEPA.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pharmacy = request.user

        sub, _created = Subscription.objects.get_or_create(pharmacy=pharmacy)

        # Créer le Customer Stripe si inexistant
        if not sub.stripe_customer_id:
            customer_id = StripeService.create_customer(pharmacy)
            sub.stripe_customer_id = customer_id
            sub.save(update_fields=['stripe_customer_id', 'updated_at'])

        # SetupIntent pour collecter le SEPA sans paiement immédiat
        setup_intent = stripe.SetupIntent.create(
            customer=sub.stripe_customer_id,
            payment_method_types=['sepa_debit'],
            usage='off_session',
        )

        return Response({'client_secret': setup_intent.client_secret})


class ConfirmSubscriptionView(APIView):
    """
    Appelée après que Angular a confirmé le SetupIntent SEPA.
    Attache le moyen de paiement et crée l'abonnement Stripe réel.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pharmacy = request.user
        payment_method_id = request.data.get('payment_method_id')

        if not payment_method_id:
            return Response(
                {'error': 'payment_method_id requis'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        try:
            sub = Subscription.objects.get(pharmacy=pharmacy)
        except Subscription.DoesNotExist:
            return Response(
                {'error': 'Subscription introuvable'},
                status=drf_status.HTTP_404_NOT_FOUND
            )

        # Q04 : garde anti-rejeu. Sans ça, un double POST (double-clic, retry
        # réseau) créait un SECOND abonnement Stripe et écrasait l'id du premier
        # dans sub → abonnement orphelin facturé + double prélèvement.
        if sub.stripe_subscription_id:
            return Response(
                {'error': 'Un abonnement est déjà actif pour cette pharmacie.'},
                status=drf_status.HTTP_409_CONFLICT,
            )

        # Attacher le moyen de paiement au customer
        stripe.PaymentMethod.attach(
            payment_method_id,
            customer=sub.stripe_customer_id,
        )
        stripe.Customer.modify(
            sub.stripe_customer_id,
            invoice_settings={'default_payment_method': payment_method_id},
        )

        # Plan selon le nombre de collaborateurs actifs
        collab_count = pharmacy.collaborators.filter(is_active=True).count()
        plan = 'large' if collab_count >= 10 else 'small'

        # Reliquat de l'essai ouvert à l'inscription. Sans ça, souscrire
        # relancerait 30 jours pleins : un compte ayant déjà consommé son essai
        # s'en offrirait un second en arrivant sur l'écran de paiement.
        trial_days = 0
        if sub.trial_ends_at:
            remaining = sub.trial_ends_at - datetime.now(dt_timezone.utc)
            trial_days = max(0, remaining.days)
        else:
            trial_days = Subscription.TRIAL_DAYS

        # Code promo optionnel → étend le trial
        promo_code_str = request.data.get('promo_code', '').strip()
        if promo_code_str:
            from apps.billing.promo_service import validate_and_redeem, PromoError
            try:
                promo = validate_and_redeem(promo_code_str, pharmacy)
                trial_days = promo.trial_days_total
            except PromoError as e:
                return Response({'error': str(e)},
                                status=drf_status.HTTP_400_BAD_REQUEST)

        stripe_sub = StripeService.create_subscription(
            sub.stripe_customer_id, plan, trial_days=trial_days,
        )

        sub.stripe_subscription_id = stripe_sub.id
        sub.plan = plan
        sub.status = Subscription.Status.TRIALING
        sub.trial_ends_at = datetime.fromtimestamp(
            stripe_sub.trial_end, tz=dt_timezone.utc
        )
        sub.save(update_fields=[
            'stripe_subscription_id', 'plan', 'status', 'trial_ends_at', 'updated_at'
        ])

        return Response({'status': 'subscription_created', 'plan': plan})


class SmsPackPaymentIntentView(APIView):
    """Crée un PaymentIntent CB pour l'achat d'un pack SMS."""
    permission_classes = [IsAuthenticated]

    SMS_PACKS = {
        'S': {'quantity': 100, 'amount_cents': 900},
        'M': {'quantity': 250, 'amount_cents': 2200},
        'L': {'quantity': 500, 'amount_cents': 3900},
    }

    def post(self, request):
        pack = request.data.get('pack')  # 'S' | 'M' | 'L'

        if pack not in self.SMS_PACKS:
            return Response(
                {'error': 'Pack invalide. Valeurs acceptées : S, M, L'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        pharmacy = request.user
        pack_info = self.SMS_PACKS[pack]

        payment_intent = StripeService.create_sms_payment_intent(
            amount_cents=pack_info['amount_cents'],
            pharmacy=pharmacy,
        )

        return Response({
            'client_secret': payment_intent.client_secret,
            'quantity': pack_info['quantity'],
            'amount_cents': pack_info['amount_cents'],
        })


class InvoiceListView(APIView):
    """Liste des factures de la pharmacie."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacy = request.user
        invoices = Invoice.objects.filter(pharmacy=pharmacy).order_by('-issued_at')[:24]
        return Response(InvoiceSerializer(invoices, many=True).data)


class InvoiceDownloadView(APIView):
    """Retourne une URL de téléchargement du PDF de facture.

    En prod (Scaleway S3) : URL signée temporaire ; en dev (storage local) :
    URL `/media/...` servie par la route média protégée par JWT.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):
        pharmacy = request.user
        try:
            invoice = Invoice.objects.get(id=invoice_id, pharmacy=pharmacy)
        except Invoice.DoesNotExist:
            return Response({'error': 'Facture introuvable'},
                            status=drf_status.HTTP_404_NOT_FOUND)

        if not invoice.pdf_storage_key:
            return Response({'error': 'PDF non disponible'},
                            status=drf_status.HTTP_404_NOT_FOUND)

        from django.core.files.storage import default_storage
        url = default_storage.url(invoice.pdf_storage_key)
        return Response({'download_url': url})


class ValidatePromoCodeView(APIView):
    """
    Valide un code promo sans l'appliquer.
    Permet à Angular d'afficher un aperçu avant confirmation.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [PromoValidateThrottle]

    def post(self, request):
        code = request.data.get('code', '').strip()
        if not code:
            return Response({'error': 'Code requis.'},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        try:
            promo = PromoCode.objects.get(code__iexact=code)
        except PromoCode.DoesNotExist:
            return Response({'valid': False, 'error': 'Code promo invalide.'},
                            status=drf_status.HTTP_404_NOT_FOUND)

        pharmacy = request.user
        already_used = PromoRedemption.objects.filter(
            promo_code=promo, pharmacy=pharmacy
        ).exists()

        if not promo.is_valid() or already_used:
            return Response({'valid': False, 'error': 'Ce code promo n\'est plus disponible.'},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        return Response({
            'valid':       True,
            'months_free': promo.months_free,
            'trial_days':  promo.trial_days_total,
            'message':     f'{promo.months_free} mois offerts après votre mois d\'essai.',
        })


class UpdatePaymentMethodView(APIView):
    """Change le moyen de paiement SEPA d'un abonnement existant (changer de RIB)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pharmacy = request.user
        payment_method_id = request.data.get('payment_method_id')
        if not payment_method_id:
            return Response({'error': 'payment_method_id requis'},
                            status=drf_status.HTTP_400_BAD_REQUEST)
        try:
            sub = Subscription.objects.get(pharmacy=pharmacy)
        except Subscription.DoesNotExist:
            return Response({'error': 'Abonnement introuvable'},
                            status=drf_status.HTTP_404_NOT_FOUND)
        if not sub.stripe_customer_id:
            return Response({'error': 'Aucun client Stripe associé.'},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        stripe.PaymentMethod.attach(payment_method_id, customer=sub.stripe_customer_id)
        stripe.Customer.modify(
            sub.stripe_customer_id,
            invoice_settings={'default_payment_method': payment_method_id},
        )
        if sub.stripe_subscription_id:
            stripe.Subscription.modify(
                sub.stripe_subscription_id, default_payment_method=payment_method_id,
            )
        return Response({'status': 'payment_method_updated'})


class CancelSubscriptionView(APIView):
    """Résilie l'abonnement en fin de période courante (cancel_at_period_end)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pharmacy = request.user
        try:
            sub = Subscription.objects.get(pharmacy=pharmacy)
        except Subscription.DoesNotExist:
            return Response({'error': 'Abonnement introuvable'},
                            status=drf_status.HTTP_404_NOT_FOUND)
        if not sub.stripe_subscription_id:
            return Response({'error': 'Aucun abonnement Stripe à résilier.'},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        StripeService.cancel_subscription(sub.stripe_subscription_id)
        sub.cancel_at_period_end = True
        sub.save(update_fields=['cancel_at_period_end', 'updated_at'])
        return Response({
            'status': 'cancellation_scheduled',
            'current_period_end': sub.current_period_end,
        })


class ResumeSubscriptionView(APIView):
    """Annule la résiliation programmée (reprend l'abonnement)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pharmacy = request.user
        try:
            sub = Subscription.objects.get(pharmacy=pharmacy)
        except Subscription.DoesNotExist:
            return Response({'error': 'Abonnement introuvable'},
                            status=drf_status.HTTP_404_NOT_FOUND)
        if sub.stripe_subscription_id:
            stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=False)
        sub.cancel_at_period_end = False
        sub.save(update_fields=['cancel_at_period_end', 'updated_at'])
        return Response({'status': 'resumed'})
