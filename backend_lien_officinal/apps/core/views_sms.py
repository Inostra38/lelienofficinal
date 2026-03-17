from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import SMSTemplate, SMSLog
from .serializers_sms import (
    SMSTemplateSerializer, SMSLogSerializer,
    SMSPreviewSerializer, SMSSendSerializer,
)
from .services import TemplateResolver, OVHService


def _get_collaborator(request):
    """Lit le collaborateur actif depuis le claim JWT (auth_type='collaborator')."""
    token = request.auth
    if not token:
        return None
    if token.get('auth_type') != 'collaborator':
        return None
    collab_id = token.get('collaborator_id')
    if not collab_id:
        return None
    try:
        from apps.team.models import Collaborator
        return Collaborator.objects.get(id=int(collab_id), pharmacy=request.user, is_active=True)
    except Exception:
        return None


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
                template = SMSTemplate.objects.get(
                    id=data['template_id'], pharmacy=pharmacy
                )
                content = template.content
            except SMSTemplate.DoesNotExist:
                return Response(
                    {'detail': 'Template introuvable.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
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

    def post(self, request):
        serializer = SMSSendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        pharmacy = request.user
        template = None

        if data.get('template_id'):
            try:
                template = SMSTemplate.objects.get(
                    id=data['template_id'], pharmacy=pharmacy
                )
            except SMSTemplate.DoesNotExist:
                return Response(
                    {'detail': 'Template introuvable.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            svc = OVHService()
            svc.send_sms(
                pharmacy=pharmacy,
                to=data['to'],
                message=data['message'],
                template=template,
                recipient_civilite=data.get('recipient_civilite', ''),
                recipient_name=data.get('recipient_name', ''),
                motif=data.get('motif', ''),
            )
            pharmacy.refresh_from_db()
            return Response({'success': True, 'credits_remaining': pharmacy.sms_credits})
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f"Erreur lors de l'envoi : {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class SMSLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SMSLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SMSLog.objects.filter(pharmacy=self.request.user).order_by('-sent_at')[:50]

