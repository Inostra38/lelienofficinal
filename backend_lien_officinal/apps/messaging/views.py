from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.team.models import Collaborator
from apps.team.serializers import CollaboratorSerializer
from .models import Conversation, Message, Attachment
from .serializers import (
    ConversationSerializer,
    ConversationCreateSerializer,
    MessageSerializer,
    MessageCreateSerializer,
    AttachmentSerializer,
    AttachmentUploadSerializer,
)


def _get_collaborator(request):
    """
    Récupère le collaborateur actif depuis le header X-Collaborator-Id.
    Retourne None si absent ou invalide (contexte sans collaborateur identifié).
    """
    collab_id = request.headers.get('X-Collaborator-Id')
    if not collab_id:
        return None
    try:
        return Collaborator.objects.get(id=int(collab_id), pharmacy=request.user, is_active=True)
    except (Collaborator.DoesNotExist, ValueError):
        return None


def _get_conversation_for_participant(conversation_id, request, collaborator):
    """
    Récupère une conversation appartenant à la pharmacie ET dont
    le collaborateur actif est participant. Lève 404 sinon.
    """
    return get_object_or_404(
        Conversation,
        id=conversation_id,
        pharmacy=request.user,
        participants=collaborator,
    )


class ConversationListCreateView(APIView):
    """
    GET  /api/messaging/conversations/  — Liste des fils de la pharmacie
    POST /api/messaging/conversations/  — Créer un fil
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant ou invalide."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Filtrage par participant : on ne retourne que les conversations
        # dont le collaborateur actif est membre
        conversations = Conversation.objects.filter(
            pharmacy=request.user, participants=collaborator
        )
        serializer = ConversationSerializer(
            conversations, many=True, context={'request': request, 'collaborator': collaborator}
        )
        return Response(serializer.data)

    def post(self, request):
        serializer = ConversationCreateSerializer(
            data=request.data, context={'request': request}
        )
        if serializer.is_valid():
            conversation = serializer.save()
            return Response(
                ConversationSerializer(conversation, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ConversationDetailView(APIView):
    """
    GET    /api/messaging/conversations/{id}/  — Détail d'un fil
    DELETE /api/messaging/conversations/{id}/  — Supprimer (créateur uniquement)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant ou invalide."},
                status=status.HTTP_400_BAD_REQUEST
            )
        conversation = _get_conversation_for_participant(conversation_id, request, collaborator)
        serializer = ConversationSerializer(
            conversation, context={'request': request, 'collaborator': collaborator}
        )
        return Response(serializer.data)

    def delete(self, request, conversation_id):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant ou invalide."},
                status=status.HTTP_400_BAD_REQUEST
            )
        conversation = _get_conversation_for_participant(conversation_id, request, collaborator)

        if conversation.created_by_id != collaborator.id:
            return Response(
                {"detail": "Seul le créateur peut supprimer ce fil."},
                status=status.HTTP_403_FORBIDDEN
            )

        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageListCreateView(APIView):
    """
    GET  /api/messaging/conversations/{id}/messages/  — Messages du fil (paginés)
    POST /api/messaging/conversations/{id}/messages/  — Envoyer un message
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant ou invalide."},
                status=status.HTTP_400_BAD_REQUEST
            )
        conversation = _get_conversation_for_participant(conversation_id, request, collaborator)
        messages = conversation.messages.select_related('sender').prefetch_related(
            'attachments', 'is_read_by'
        )
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, conversation_id):
        serializer = MessageCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        collaborator = serializer.context['collaborator']
        # La vérification de participation est intégrée dans la requête
        conversation = _get_conversation_for_participant(conversation_id, request, collaborator)

        message = Message.objects.create(
            conversation=conversation,
            sender=collaborator,
            content=serializer.validated_data['content'],
        )
        return Response(
            MessageSerializer(message, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class MarkReadView(APIView):
    """
    POST /api/messaging/conversations/{id}/mark-read/
    Marque tous les messages du fil comme lus par le collaborateur actif.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant ou invalide."},
                status=status.HTTP_400_BAD_REQUEST
            )
        conversation = _get_conversation_for_participant(conversation_id, request, collaborator)

        for message in conversation.messages.exclude(sender=collaborator):
            message.is_read_by.add(collaborator)

        return Response({"detail": "Messages marqués comme lus."})


class AttachmentUploadView(APIView):
    """
    POST /api/messaging/messages/{message_id}/attachments/
    Upload d'une pièce jointe sur un message existant.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant ou invalide."},
                status=status.HTTP_400_BAD_REQUEST
            )
        message = get_object_or_404(
            Message,
            id=message_id,
            conversation__pharmacy=request.user,
            conversation__participants=collaborator,
        )
        serializer = AttachmentUploadSerializer(
            data=request.data, context={'message': message}
        )
        if serializer.is_valid():
            attachment = serializer.save()
            return Response(
                AttachmentSerializer(attachment).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AttachmentDownloadView(APIView):
    """
    GET /api/messaging/attachments/{attachment_id}/download/
    Télécharge une pièce jointe (scope pharmacie vérifié).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, attachment_id):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant ou invalide."},
                status=status.HTTP_400_BAD_REQUEST
            )
        attachment = get_object_or_404(
            Attachment,
            id=attachment_id,
            message__conversation__pharmacy=request.user,
            message__conversation__participants=collaborator,
        )
        response = FileResponse(
            attachment.file.open('rb'),
            content_type=attachment.file_type,
        )
        response['Content-Disposition'] = f'attachment; filename="{attachment.file_name}"'
        return response


class TeamMembersView(APIView):
    """
    GET /api/messaging/team-members/
    Liste des collaborateurs actifs de la pharmacie (pour le sélecteur de participants).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        collaborators = Collaborator.objects.filter(
            pharmacy=request.user, is_active=True
        ).order_by('first_name', 'last_name')
        serializer = CollaboratorSerializer(collaborators, many=True)
        return Response(serializer.data)
