import logging
from rest_framework import viewsets, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import UserRateThrottle, SimpleRateThrottle

logger = logging.getLogger(__name__)
from django.db.models import F
from django.utils import timezone

from .models import SMSTemplate, SMSLog
from .serializers_sms import (
    SMSTemplateSerializer, SMSLogSerializer,
    SMSPreviewSerializer, SMSSendSerializer,
)
from .services import TemplateResolver, OVHService
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


# IPs officielles OVH SMS (Europe)
_OVH_SMS_IPS = frozenset({
    '46.105.152.56', '46.105.152.57', '46.105.152.58',
    '46.105.152.59', '46.105.152.60', '46.105.152.61',
    '46.105.152.62', '46.105.152.63',
    '87.98.129.90',  '87.98.129.91',
})


class SMSTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = SMSTemplateSerializer
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
        sms_count = OVHService.count_sms(result['preview_text'])
        encoding = 'GSM-7' if OVHService.is_gsm7(result['preview_text']) else 'Unicode'

        return Response({
            'preview_text': result['preview_text'],
            'missing_vars': result['missing_vars'],
            'sms_count': sms_count,
            'encoding': encoding,
        })


class SMSSendView(APIView):
    permission_classes = [IsAuthenticated]
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

        credits_needed = OVHService.count_sms(data['message'])

        # Déduction atomique (race-condition safe)
        updated = pharmacy.__class__.objects.filter(
            pk=pharmacy.pk, sms_credits__gte=credits_needed
        ).update(sms_credits=F('sms_credits') - credits_needed)

        if not updated:
            return Response(
                {'error': f'Crédits insuffisants : {credits_needed} requis.'},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        pharmacy.refresh_from_db(fields=['sms_credits'])

        if pharmacy.sms_credits < 10:
            logger.warning(
                "Crédits SMS bas — pharmacy_id=%s nom=%s credits=%s",
                pharmacy.id, pharmacy.nom_officine, pharmacy.sms_credits,
            )

        phone = data['to'].replace(' ', '')
        to_hash = OVHService.hash_phone(phone)

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

        from .tasks import send_sms_task
        send_sms_task.delay(log.id, phone, data['message'])

        return Response(
            {'log_id': log.id, 'credits_remaining': pharmacy.sms_credits},
            status=status.HTTP_202_ACCEPTED,
        )


class SMSLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SMSLogSerializer
    permission_classes = [IsAuthenticated]
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
    Accusé de réception OVH — endpoint public.
    Sécurité :
      1. Token dans le path URL (/api/sms/webhook/<token>/) — invisible dans les logs query params
      2. Whitelist IPs OVH (optionnelle, activée si SMS_OVH_IP_WHITELIST=true)
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token=''):
        return self._handle(request, token)

    def post(self, request, token=''):
        return self._handle(request, token)

    def _handle(self, request, token):
        from django.conf import settings as s

        # 1. Vérification du token dans le path
        secret = getattr(s, 'SMS_WEBHOOK_SECRET', '')
        if secret and token != secret:
            return Response(status=status.HTTP_403_FORBIDDEN)

        # 2. Whitelist IPs OVH (optionnelle)
        if getattr(s, 'SMS_OVH_IP_WHITELIST', False):
            client_ip = (
                request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                or request.META.get('REMOTE_ADDR', '')
            )
            if client_ip not in _OVH_SMS_IPS:
                logger.warning("[SMS Webhook] IP non autorisée : %s", client_ip)
                return Response(status=status.HTTP_403_FORBIDDEN)

        # OVH envoie : msgid, status (OK/KO)
        msgid = request.query_params.get('msgid') or request.data.get('msgid', '')
        ovh_status = request.query_params.get('status') or request.data.get('status', '')

        if not msgid:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        new_status = (
            SMSLog.Status.DELIVERED if ovh_status == 'OK' else SMSLog.Status.FAILED
        )

        try:
            log = SMSLog.objects.get(ovh_message_id=msgid)
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        request.user.refresh_from_db(fields=['sms_credits'])
        return Response({'credits': request.user.sms_credits})


class SMSStatsView(APIView):
    """Statistiques SMS de la pharmacie — compteurs calculés en DB."""
    permission_classes = [IsAuthenticated]

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
