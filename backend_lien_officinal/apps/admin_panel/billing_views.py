"""
Vues admin (panneau SaaS) pour la gestion des abonnements et codes promo.
Protégées par l'auth admin (JWT + TOTP + IP whitelist) et journalisées.
"""
import logging
from datetime import datetime, timezone as dt_timezone

from django.db.models import Q
from django.utils import timezone
from rest_framework import status as drf_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Pharmacy
from apps.billing.models import Subscription, Invoice, PromoCode

from .authentication import AdminJWTAuthentication
from .views import _audit

logger = logging.getLogger(__name__)

# Échéance « à vie » pour les abonnements offerts (comp, sans Stripe).
COMP_PERIOD_END = datetime(2125, 1, 1, tzinfo=dt_timezone.utc)


def _sub_payload(sub):
    if sub is None:
        return None
    return {
        'plan': sub.plan,
        'plan_display': sub.get_plan_display(),
        'status': sub.status,
        'status_display': sub.get_status_display(),
        'is_comp': not sub.stripe_subscription_id,
        'trial_ends_at': sub.trial_ends_at,
        'current_period_end': sub.current_period_end,
    }


def _get_sub(pharmacy):
    try:
        return pharmacy.subscription
    except Subscription.DoesNotExist:
        return None


def _row(pharmacy, sub):
    return {
        'pharmacy_id': pharmacy.id,
        'email': pharmacy.email,
        'nom_officine': pharmacy.nom_officine,
        'sms_credits': pharmacy.sms_credits,
        'subscription': _sub_payload(sub),
    }


class AdminSubscriptionListView(APIView):
    """GET /api/admin/subscriptions/?q=&limit= → pharmacies + statut d'abonnement."""
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        limit = min(int(request.query_params.get('limit', 50)), 200)

        qs = Pharmacy.objects.all()
        if q:
            qs = qs.filter(Q(email__icontains=q) | Q(nom_officine__icontains=q))
        qs = qs.select_related('subscription').order_by('nom_officine', 'email')

        total = qs.count()
        rows = [_row(p, _get_sub(p)) for p in qs[:limit]]
        return Response({'count': total, 'results': rows})


class AdminSubscriptionDetailView(APIView):
    """GET /api/admin/subscriptions/<pharmacy_id>/ → détail + factures."""
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pharmacy_id):
        try:
            pharmacy = Pharmacy.objects.select_related('subscription').get(id=pharmacy_id)
        except Pharmacy.DoesNotExist:
            return Response({'error': 'Pharmacie introuvable.'}, status=drf_status.HTTP_404_NOT_FOUND)

        invoices = Invoice.objects.filter(pharmacy=pharmacy).order_by('-issued_at')[:24]
        invoices_data = [{
            'id': inv.id,
            'invoice_number': inv.invoice_number,
            'invoice_type': inv.invoice_type,
            'amount_ttc': str(inv.amount_ttc),
            'issued_at': inv.issued_at,
            'paid_at': inv.paid_at,
        } for inv in invoices]

        row = _row(pharmacy, _get_sub(pharmacy))
        row['invoices'] = invoices_data
        return Response(row)


class AdminSubscriptionActionView(APIView):
    """
    POST /api/admin/subscriptions/<pharmacy_id>/action/
    body : { action: grant_free | revoke | change_plan | suspend | reactivate, plan? }
    """
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pharmacy_id):
        try:
            pharmacy = Pharmacy.objects.select_related('subscription').get(id=pharmacy_id)
        except Pharmacy.DoesNotExist:
            return Response({'error': 'Pharmacie introuvable.'}, status=drf_status.HTTP_404_NOT_FOUND)

        action = request.data.get('action', '')
        try:
            sub = pharmacy.subscription
        except Subscription.DoesNotExist:
            sub = None

        if action == 'grant_free':
            plan = request.data.get('plan', 'small')
            if plan not in ('small', 'large'):
                plan = 'small'
            sub, _created = Subscription.objects.update_or_create(
                pharmacy=pharmacy,
                defaults={
                    'plan': plan,
                    'status': Subscription.Status.ACTIVE,
                    'stripe_subscription_id': None,
                    'trial_ends_at': None,
                    'current_period_end': COMP_PERIOD_END,
                    'suspended_at': None,
                },
            )
            _audit('SUBSCRIPTION_UPDATE', request,
                   detail=f"grant_free {pharmacy.email} (plan={plan})")

        elif action == 'revoke':
            if sub is None:
                return Response({'error': 'Aucun abonnement à révoquer.'},
                                status=drf_status.HTTP_400_BAD_REQUEST)
            if sub.stripe_subscription_id:
                return Response(
                    {'error': 'Abonnement Stripe réel : à gérer via Stripe, pas révocable ici.'},
                    status=drf_status.HTTP_400_BAD_REQUEST)
            sub.delete()
            sub = None
            _audit('SUBSCRIPTION_UPDATE', request, detail=f"revoke {pharmacy.email}")

        elif action == 'change_plan':
            if sub is None:
                return Response({'error': 'Aucun abonnement.'}, status=drf_status.HTTP_400_BAD_REQUEST)
            new_plan = request.data.get('plan', '')
            if new_plan not in ('small', 'large'):
                return Response({'error': 'Plan invalide (small | large).'},
                                status=drf_status.HTTP_400_BAD_REQUEST)
            if sub.stripe_subscription_id:
                try:
                    from apps.billing.stripe_service import StripeService
                    StripeService.update_subscription_plan(sub.stripe_subscription_id, new_plan)
                except Exception as exc:
                    logger.exception('admin change_plan Stripe error: %s', exc)
                    return Response({'error': 'Échec Stripe lors du changement de plan.'},
                                    status=drf_status.HTTP_502_BAD_GATEWAY)
            sub.plan = new_plan
            sub.save(update_fields=['plan', 'updated_at'])
            _audit('SUBSCRIPTION_UPDATE', request,
                   detail=f"change_plan {pharmacy.email} → {new_plan}")

        elif action == 'suspend':
            if sub is None:
                return Response({'error': 'Aucun abonnement.'}, status=drf_status.HTTP_400_BAD_REQUEST)
            sub.status = Subscription.Status.SUSPENDED
            sub.suspended_at = timezone.now()
            sub.save(update_fields=['status', 'suspended_at', 'updated_at'])
            _audit('SUBSCRIPTION_UPDATE', request, detail=f"suspend {pharmacy.email}")

        elif action == 'reactivate':
            if sub is None:
                return Response({'error': 'Aucun abonnement.'}, status=drf_status.HTTP_400_BAD_REQUEST)
            sub.status = Subscription.Status.ACTIVE
            sub.suspended_at = None
            sub.save(update_fields=['status', 'suspended_at', 'updated_at'])
            _audit('SUBSCRIPTION_UPDATE', request, detail=f"reactivate {pharmacy.email}")

        else:
            return Response({'error': 'Action inconnue.'}, status=drf_status.HTTP_400_BAD_REQUEST)

        return Response(_row(pharmacy, sub))


# ── Codes promo ───────────────────────────────────────────────────────────────

def _promo_payload(promo):
    return {
        'id': promo.id,
        'code': promo.code,
        'months_free': promo.months_free,
        'is_active': promo.is_active,
        'max_uses': promo.max_uses,
        'current_uses': promo.current_uses,
        'expires_at': promo.expires_at,
        'note': promo.note,
        'created_at': promo.created_at,
    }


class AdminPromoCodeListCreateView(APIView):
    """GET liste / POST création de codes promo."""
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        promos = PromoCode.objects.all().order_by('-created_at')
        return Response([_promo_payload(p) for p in promos])

    def post(self, request):
        code = request.data.get('code', '').strip().upper()
        if not code:
            return Response({'error': 'Code requis.'}, status=drf_status.HTTP_400_BAD_REQUEST)
        if PromoCode.objects.filter(code__iexact=code).exists():
            return Response({'error': 'Ce code existe déjà.'}, status=drf_status.HTTP_400_BAD_REQUEST)
        try:
            months_free = int(request.data.get('months_free', 0))
        except (TypeError, ValueError):
            months_free = 0
        if months_free < 1:
            return Response({'error': 'months_free doit être ≥ 1.'},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        max_uses = request.data.get('max_uses')
        promo = PromoCode.objects.create(
            code=code,
            months_free=months_free,
            max_uses=int(max_uses) if max_uses not in (None, '', 0) else None,
            note=request.data.get('note', ''),
            is_active=bool(request.data.get('is_active', True)),
        )
        _audit('PROMO_UPDATE', request, detail=f"create {code} (months_free={months_free})")
        return Response(_promo_payload(promo), status=drf_status.HTTP_201_CREATED)


class AdminPromoCodeDetailView(APIView):
    """PATCH (toggle/maj) / DELETE d'un code promo."""
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, promo_id):
        try:
            promo = PromoCode.objects.get(id=promo_id)
        except PromoCode.DoesNotExist:
            return Response({'error': 'Code introuvable.'}, status=drf_status.HTTP_404_NOT_FOUND)

        if 'is_active' in request.data:
            promo.is_active = bool(request.data.get('is_active'))
        if 'note' in request.data:
            promo.note = request.data.get('note', '')
        if 'max_uses' in request.data:
            mu = request.data.get('max_uses')
            promo.max_uses = int(mu) if mu not in (None, '', 0) else None
        promo.save()
        _audit('PROMO_UPDATE', request, detail=f"update {promo.code}")
        return Response(_promo_payload(promo))

    def delete(self, request, promo_id):
        try:
            promo = PromoCode.objects.get(id=promo_id)
        except PromoCode.DoesNotExist:
            return Response({'error': 'Code introuvable.'}, status=drf_status.HTTP_404_NOT_FOUND)
        code = promo.code
        promo.delete()
        _audit('PROMO_UPDATE', request, detail=f"delete {code}")
        return Response(status=drf_status.HTTP_204_NO_CONTENT)
