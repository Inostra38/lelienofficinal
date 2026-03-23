from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import UserRateThrottle
from django.db.models import F

from .models import SMSTemplate, SMSLog
from .serializers_sms import (
    SMSTemplateSerializer, SMSLogSerializer,
    SMSPreviewSerializer, SMSSendSerializer,
)
from .services import TemplateResolver, OVHService


def _get_collaborator(request):
    """Lit le collaborateur actif depuis le claim JWT (auth_type='collaborator')."""
    token = request.auth
    if not token or token.get('auth_type') != 'collaborator':
        return None
    collab_id = token.get('collaborator_id')
    if not collab_id:
        return None
    try:
        from apps.team.models import Collaborator
        return Collaborator.objects.get(id=int(collab_id), pharmacy=request.user, is_active=True)
    except Exception:
        return None


class SMSSendThrottle(UserRateThrottle):
    scope = 'sms_send'


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
    throttle_classes = [SMSSendThrottle]

    def post(self, request):
        serializer = SMSSendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        pharmacy = request.user
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
        phone = data['to'].replace(' ', '')
        to_hash = OVHService.hash_phone(phone)

        log = SMSLog.objects.create(
            pharmacy=pharmacy,
            template=template,
            sent_by=pharmacy,
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

    def get_queryset(self):
        return (
            SMSLog.objects
            .filter(pharmacy=self.request.user)
            .select_related('template', 'sent_by')
            .order_by('-sent_at')[:100]
        )


class SMSWebhookView(APIView):
    """Accusé de réception OVH — endpoint public protégé par secret."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return self._handle(request)

    def post(self, request):
        return self._handle(request)

    def _handle(self, request):
        from django.conf import settings as s
        secret = getattr(s, 'SMS_WEBHOOK_SECRET', '')
        if secret and request.query_params.get('secret') != secret:
            return Response(status=status.HTTP_403_FORBIDDEN)

        # OVH envoie : msgid, status (OK/KO)
        msgid = request.query_params.get('msgid') or request.data.get('msgid', '')
        ovh_status = request.query_params.get('status') or request.data.get('status', '')

        if not msgid:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        new_status = (
            SMSLog.Status.DELIVERED if ovh_status == 'OK' else SMSLog.Status.FAILED
        )
        SMSLog.objects.filter(ovh_message_id=msgid).update(status=new_status)

        return Response(status=status.HTTP_200_OK)


class SMSCreditsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        request.user.refresh_from_db(fields=['sms_credits'])
        return Response({'credits': request.user.sms_credits})
