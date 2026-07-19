from django.db.models import Count, IntegerField, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from apps.billing.permissions import HasPaidAccess
from apps.core.auth_helpers import get_collaborator_from_jwt as _get_collaborator


class MessagingThrottle(UserRateThrottle):
    scope = 'messaging'

from apps.team.models import Collaborator
from apps.team.serializers import CollaboratorSerializer
from .models import Conversation, Message
from .serializers import (
    ConversationSerializer,
    ConversationCreateSerializer,
    MessageSerializer,
    MessageCreateSerializer,
)


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
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def get(self, request):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant ou invalide."},
                status=status.HTTP_400_BAD_REQUEST
            )
        conversations = Conversation.objects.filter(
            pharmacy=request.user, participants=collaborator
        ).exclude(hidden_by=collaborator)

        # BLOC 2 — annotation unread_count : 1 sous-requête SQL au lieu de N COUNT()
        unread_sq = (
            Message.objects
            .filter(conversation_id=OuterRef('pk'))
            .exclude(is_read_by=collaborator)
            .exclude(sender=collaborator)
            .values('conversation_id')
            .annotate(cnt=Count('id'))
            .values('cnt')
        )
        conversations = conversations.annotate(
            unread_count_ann=Subquery(unread_sq, output_field=IntegerField())
        )

        serializer = ConversationSerializer(
            conversations, many=True, context={'request': request, 'collaborator': collaborator}
        )
        return Response(serializer.data)

    def post(self, request):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "Session collaborateur requise."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = ConversationCreateSerializer(
            data=request.data, context={'request': request, 'collaborator': collaborator}
        )
        if serializer.is_valid():
            conversation = serializer.save()
            return Response(
                ConversationSerializer(conversation, context={'request': request, 'collaborator': collaborator}).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ConversationDetailView(APIView):
    """
    GET    /api/messaging/conversations/{id}/  — Détail d'un fil
    DELETE /api/messaging/conversations/{id}/  — Supprimer (créateur uniquement)
    """
    permission_classes = [IsAuthenticated, HasPaidAccess]

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
    GET  /api/messaging/conversations/{id}/messages/  — Messages du fil
    POST /api/messaging/conversations/{id}/messages/  — Envoyer un message (fallback HTTP)
    """
    permission_classes = [IsAuthenticated, HasPaidAccess]
    throttle_classes = [MessagingThrottle]

    def get(self, request, conversation_id):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant ou invalide."},
                status=status.HTTP_400_BAD_REQUEST
            )
        conversation = _get_conversation_for_participant(conversation_id, request, collaborator)
        messages = conversation.messages.select_related('sender').prefetch_related('is_read_by')
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, conversation_id):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "Session collaborateur requise."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = MessageCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        conversation = _get_conversation_for_participant(conversation_id, request, collaborator)
        message = Message.objects.create(
            conversation=conversation,
            sender=collaborator,
            content=serializer.validated_data['content'],
        )
        # Q07 : réapparition automatique, cohérente avec le chemin WebSocket
        # (consumers.save_message). Sans ça, une conversation masquée par un
        # participant ne réapparaissait pas quand un message arrivait via HTTP.
        conversation.hidden_by.clear()
        return Response(
            MessageSerializer(message, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class MarkReadView(APIView):
    """
    POST /api/messaging/conversations/{id}/mark-read/
    Marque tous les messages du fil comme lus par le collaborateur actif.
    """
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def post(self, request, conversation_id):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "En-tête X-Collaborator-Id manquant ou invalide."},
                status=status.HTTP_400_BAD_REQUEST
            )
        conversation = _get_conversation_for_participant(conversation_id, request, collaborator)

        # BLOC 1 — bulk_create : 2 requêtes au lieu de N INSERT M2M
        ThroughModel = Message.is_read_by.through
        message_ids = list(
            conversation.messages
            .exclude(sender=collaborator)
            .exclude(is_read_by=collaborator)
            .values_list("id", flat=True)
        )
        if message_ids:
            ThroughModel.objects.bulk_create(
                [ThroughModel(message_id=mid, collaborator_id=collaborator.id) for mid in message_ids],
                ignore_conflicts=True,
            )

        return Response({"detail": "Messages marqués comme lus."})


class ConversationHideView(APIView):
    """
    POST /api/messaging/conversations/{id}/hide/
    Masque la conversation pour le collaborateur actif (soft delete personnel).
    Réservé aux participants non-créateurs.
    """
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def post(self, request, conversation_id):
        collaborator = _get_collaborator(request)
        if collaborator is None:
            return Response(
                {"detail": "Session collaborateur requise."},
                status=status.HTTP_403_FORBIDDEN
            )
        conversation = _get_conversation_for_participant(conversation_id, request, collaborator)

        if conversation.created_by_id == collaborator.id:
            return Response(
                {"detail": "Le créateur doit supprimer la conversation, pas la masquer."},
                status=status.HTTP_400_BAD_REQUEST
            )

        conversation.hidden_by.add(collaborator)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeamMembersView(APIView):
    """
    GET /api/messaging/team-members/
    Liste des collaborateurs actifs de la pharmacie (pour le sélecteur de participants).
    """
    permission_classes = [IsAuthenticated, HasPaidAccess]

    def get(self, request):
        collaborators = Collaborator.objects.filter(
            pharmacy=request.user, is_active=True
        ).order_by('first_name', 'last_name')
        serializer = CollaboratorSerializer(collaborators, many=True)
        return Response(serializer.data)
