import json
import time
from collections import defaultdict, deque

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import Conversation, Message

# Rate limiting WebSocket : 30 messages par minute par collaborateur
_WS_RATE_LIMIT = 30
_WS_RATE_WINDOW = 60  # secondes
_ws_message_timestamps: dict[int, deque] = defaultdict(deque)


def _is_rate_limited(collaborator_id: int) -> bool:
    now = time.monotonic()
    timestamps = _ws_message_timestamps[collaborator_id]
    # Supprime les timestamps hors de la fenêtre
    while timestamps and now - timestamps[0] > _WS_RATE_WINDOW:
        timestamps.popleft()
    if len(timestamps) >= _WS_RATE_LIMIT:
        return True
    timestamps.append(now)
    return False


class ConversationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        collaborator = self.scope.get('collaborator')

        if not collaborator:
            await self.close(code=4001)
            return

        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.collaborator = collaborator

        is_authorized = await self.check_authorization(collaborator, self.conversation_id)
        if not is_authorized:
            await self.close(code=4003)
            return

        self.room_group_name = f'conversation_{self.conversation_id}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            content = data.get('content', '').strip()
            if not content:
                return

            if _is_rate_limited(self.collaborator.id):
                await self.send(text_data=json.dumps({
                    'error': 'rate_limited',
                    'detail': 'Trop de messages. Merci de patienter.'
                }))
                return

            message = await self.save_message(self.collaborator, self.conversation_id, content)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': str(message.id),
                        'sender': {
                            'id': self.collaborator.id,
                            'first_name': self.collaborator.first_name,
                            'last_name': self.collaborator.last_name,
                            'full_name': f'{self.collaborator.first_name} {self.collaborator.last_name}',
                            'role': self.collaborator.role,
                            'color': self.collaborator.color,
                        },
                        'content': content,
                        'created_at': message.created_at.isoformat(),
                        'is_read_by': [],
                    }
                }
            )
        except (json.JSONDecodeError, KeyError):
            pass

    async def chat_message(self, event):
        """Handler appelé par group_send — relaie le message au client WS."""
        await self.send(text_data=json.dumps(event['message']))

    # === Helpers DB ===

    @database_sync_to_async
    def check_authorization(self, collaborator, conversation_id):
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            return (
                conversation.pharmacy_id == collaborator.pharmacy_id and
                conversation.participants.filter(id=collaborator.id).exists()
            )
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, collaborator, conversation_id, content):
        conversation = Conversation.objects.get(id=conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender=collaborator,
            content=content,
        )
        # Réapparition automatique : retire tous les masquages
        # La conversation réapparaît pour les participants qui l'avaient masquée
        conversation.hidden_by.clear()
        # Message.save() met à jour conversation.updated_at automatiquement
        return message
