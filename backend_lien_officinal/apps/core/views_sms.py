import hmac
import logging
from rest_framework import viewsets, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import UserRateThrottle, SimpleRateThrottle
from apps.billing.permissions import HasPaidAccess

logger = logging.getLogger(__name__)
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import SMSTemplate, SMSLog
from .serializers_sms import (
    SMSTemplateSerializer, SMSLogSerializer,
    SMSPreviewSerializer, SMSSendSerializer,
)
from .services import TemplateResolver, SMSPartnerService
from .auth_helpers import get_collaborator_from_jwt as _get_collaborator


class SMSLogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class SMSSendThrottle(UserRateThrottle):
    """Rate limit global par pharmacie (200/heure)."""
    scope = 'sms_send'


class SMSCollaboratorThrottle(SimpleRateThrottle):
    """Rate limit par collaborateur connecté (50/heure)."""
    scope = 'sms_send_collaborator'
    rate = '50/hour'

    def get_cache_key(self, request, view):
        token = getattr(request, 'auth', None)
        if not token:
            return None
        collab_id = token.get('collaborator_id') if hasattr(token, 'get') else None
        if not collab_id:
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'collab_{collab_id}',
        }



class SMSTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = SMSTemplateSerializer
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def get_queryset(self):
        return SMSTemplate.objects.filter(pharmacy=self.request.user).order_by('title')

    def perform_create(self, serializer):
        serializer.save(pharmacy=self.request.user)

    def get_object(self):
        obj = super().get_object()
        if obj.pharmacy != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        return obj


class SMSPreviewView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def post(self, request):
        serializer = SMSPreviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        pharmacy = request.user
        collaborator = _get_collaborator(request)

        if data.get('template_id'):
            try:
                template = SMSTemplate.objects.get(id=data['template_id'], pharmacy=pharmacy)
                content = template.content
            except SMSTemplate.DoesNotExist:
                return Response({'detail': 'Template introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            content = data['content']

        resolver = TemplateResolver()
        result = resolver.resolve(
            content, pharmacy,
            custom_vars=data.get('custom_vars', {}),
            collaborator=collaborator,
        )
        sms_count = SMSPartnerService.count_sms(result['preview_text'])
        encoding = 'GSM-7' if SMSPartnerService.is_gsm7(result['preview_text']) else 'Unicode'

        return Response({
            'preview_text': result['preview_text'],
            'missing_vars': result['missing_vars'],
            'sms_count': sms_count,
            'encoding': encoding,
        })


class SMSSendView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]
    throttle_classes = [SMSSendThrottle, SMSCollaboratorThrottle]

    def post(self, request):
        serializer = SMSSendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        pharmacy = request.user
        collaborator = _get_collaborator(request)
        template = None

        if data.get('template_id'):
            try:
                template = SMSTemplate.objects.get(id=data['template_id'], pharmacy=pharmacy)
            except SMSTemplate.DoesNotExist:
                return Response({'detail': 'Template introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        credits_needed = SMSPartnerService.count_sms(data['message'])
        phone = data['to'].replace(' ', '')
        to_hash = SMSPartnerService.hash_phone(phone)

        from .tasks import send_sms_task
        from apps.billing.models import SmsCreditTransaction

        # C18 : débit + log + registre de crédits dans UNE transaction. Avant,
        # le débit (commité seul) puis la création du log étaient séparés : si le
        # log échouait, les crédits étaient perdus. C21 : on journalise le débit
        # dans SmsCreditTransaction (piste d'audit des mouvements de crédits).
        with transaction.atomic():
            # Déduction atomique (race-condition safe)
            updated = pharmacy.__class__.objects.filter(
                pk=pharmacy.pk, sms_credits__gte=credits_needed
            ).update(sms_credits=F('sms_credits') - credits_needed)

            if not updated:
                return Response(
                    {'error': f'Crédits insuffisants : {credits_needed} requis.'},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

            log = SMSLog.objects.create(
                pharmacy=pharmacy,
                template=template,
                sent_by=collaborator,
                to_hash=to_hash,
                recipient_civilite=data.get('recipient_civilite', ''),
                recipient_name=data.get('recipient_name', ''),
                motif=data.get('motif', ''),
                status=SMSLog.Status.PENDING,
                credits_used=credits_needed,
            )
            SmsCreditTransaction.objects.create(
                pharmacy=pharmacy, delta=-credits_needed,
                reason=SmsCreditTransaction.Reason.SEND, note=f'SMS log #{log.id}',
            )

        # Le bloc a commité (débit + log + registre) : on enqueue seulement
        # maintenant. Si la transaction avait échoué, l'exception serait remontée
        # et on ne serait pas ici → pas de tâche orpheline sur des crédits annulés.
        send_sms_task.delay(log.id, phone, data['message'])

        pharmacy.refresh_from_db(fields=['sms_credits'])
        if pharmacy.sms_credits < 10:
            logger.warning(
                "Crédits SMS bas — pharmacy_id=%s nom=%s credits=%s",
                pharmacy.id, pharmacy.nom_officine, pharmacy.sms_credits,
            )

        return Response(
            {'log_id': log.id, 'credits_remaining': pharmacy.sms_credits},
            status=status.HTTP_202_ACCEPTED,
        )


class SMSLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SMSLogSerializer
    permission_classes = [IsAuthenticated, HasPaidAccess]
    pagination_class = SMSLogPagination

    def get_queryset(self):
        return (
            SMSLog.objects
            .filter(pharmacy=self.request.user)
            .select_related('template', 'sent_by')
            .order_by('-sent_at')
        )


class SMSWebhookView(APIView):
    """
    Accusé de réception SMS Partner — endpoint public.
    Sécurité : token dans le path URL (/api/sms/webhook/<token>/).
    SMS Partner envoie un POST avec messageId et status (1=livré, autres=échec).
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token=''):
        return self._handle(request, token)

    def post(self, request, token=''):
        return self._handle(request, token)

    def _handle(self, request, token):
        from django.conf import settings as s

        # Vérification du token dans le path (M2)
        # Fail-closed : si le secret n'est pas configuré, on REFUSE au lieu
        # d'accepter aveuglément (avant, secret vide = vérification ignorée →
        # n'importe qui pouvait falsifier les accusés de réception).
        secret = getattr(s, 'SMS_WEBHOOK_SECRET', '')
        if not secret:
            return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        # Comparaison à temps constant (anti timing-attack).
        if not hmac.compare_digest(str(token), str(secret)):
            return Response(status=status.HTTP_403_FORBIDDEN)

        # SMS Partner envoie messageId + status
        msgid = (
            request.query_params.get('messageId')
            or request.data.get('messageId', '')
            or request.query_params.get('msgid')
            or request.data.get('msgid', '')
        )
        raw_status = (
            request.query_params.get('status')
            or request.data.get('status', '')
        )

        if not msgid:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # status=1 → livré ; tout autre valeur → échec
        try:
            delivered = int(raw_status) == 1
        except (ValueError, TypeError):
            delivered = str(raw_status).upper() == 'OK'

        new_status = SMSLog.Status.DELIVERED if delivered else SMSLog.Status.FAILED

        try:
            log = SMSLog.objects.get(provider_message_id=msgid)
        except SMSLog.DoesNotExist:
            return Response(status=status.HTTP_200_OK)

        log.status = new_status
        log.save(update_fields=['status'])

        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from django.utils import timezone as tz
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'sms_status_{log.pharmacy_id}',
                {
                    'type': 'sms_status_update',
                    'log_id': str(log.id),
                    'status': log.status,
                    'updated_at': tz.now().isoformat(),
                },
            )
        except Exception:
            pass  # Ne pas bloquer la réponse webhook si Redis est indisponible

        return Response(status=status.HTTP_200_OK)


class SMSCreditsView(APIView):
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def get(self, request):
        request.user.refresh_from_db(fields=['sms_credits'])
        return Response({'credits': request.user.sms_credits})


class SMSStatsView(APIView):
    """Statistiques SMS de la pharmacie — compteurs calculés en DB."""
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def get(self, request):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        qs = SMSLog.objects.filter(pharmacy=request.user)
        total = qs.count()
        monthly = qs.filter(sent_at__gte=month_start).count()

        return Response({
            'total_count': total,
            'monthly_count': monthly,
        })
