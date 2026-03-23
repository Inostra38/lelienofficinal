from rest_framework import serializers
from .models import Conversation, Message
from apps.team.models import Collaborator


class CollaboratorMinimalSerializer(serializers.ModelSerializer):
    """Représentation légère d'un collaborateur pour la messagerie."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Collaborator
        fields = ['id', 'first_name', 'last_name', 'full_name', 'role', 'color']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class MessageSerializer(serializers.ModelSerializer):
    sender = CollaboratorMinimalSerializer(read_only=True)
    is_read_by = CollaboratorMinimalSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'sender', 'content', 'is_read_by', 'created_at']


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['content']

    def validate_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Le message ne peut pas être vide.")
        return value


class ConversationSerializer(serializers.ModelSerializer):
    created_by = CollaboratorMinimalSerializer(read_only=True)
    participants = CollaboratorMinimalSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'subject', 'created_by', 'participants',
            'last_message', 'unread_count', 'created_at', 'updated_at'
        ]

    def get_last_message(self, obj):
        msg = obj.messages.last()
        if not msg:
            return None
        return {
            'sender': f"{msg.sender.first_name} {msg.sender.last_name}" if msg.sender else "—",
            'content': msg.content[:80] if msg.content else "",
            'created_at': msg.created_at,
        }

    def get_unread_count(self, obj):
        """
        Nombre de messages non lus. Utilise l'annotation `unread_count_ann` si disponible
        (injectée par la vue en 1 sous-requête), sinon fallback sur COUNT() individuel.
        """
        if hasattr(obj, 'unread_count_ann'):
            return obj.unread_count_ann or 0
        collaborator = self.context.get('collaborator')
        if not collaborator:
            return 0
        return obj.messages.exclude(is_read_by=collaborator).exclude(sender=collaborator).count()


class ConversationCreateSerializer(serializers.ModelSerializer):
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, min_length=1
    )

    class Meta:
        model = Conversation
        fields = ['subject', 'participant_ids']

    def validate_subject(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Le sujet est obligatoire.")
        return value.strip()

    def validate_participant_ids(self, value):
        request = self.context['request']
        collaborators = Collaborator.objects.filter(
            id__in=value, pharmacy=request.user, is_active=True
        )
        if collaborators.count() != len(set(value)):
            raise serializers.ValidationError(
                "Un ou plusieurs participants n'appartiennent pas à cette pharmacie."
            )
        self.context['participants'] = list(collaborators)
        return value

    def create(self, validated_data):
        validated_data.pop('participant_ids')
        creator = self.context['collaborator']
        participants = self.context['participants']

        conversation = Conversation.objects.create(
            pharmacy=self.context['request'].user,
            subject=validated_data['subject'],
            created_by=creator,
        )
        # Le créateur est aussi participant
        all_participants = list({p.id: p for p in [creator] + participants}.values())
        conversation.participants.set(all_participants)
        return conversation
