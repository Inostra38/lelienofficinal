import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.billing.permissions import (
    WS_CLOSE_PAYMENT_REQUIRED,
    pharmacy_has_paid_access,
)


class SMSStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket en lecture seule : pousse les mises à jour de statut SMS
    en temps réel après accusé de réception OVH.
    Groupe scopé par pharmacie : sms_status_{pharmacy_id}
    """

    async def connect(self):
        collaborator = self.scope.get('collaborator')
        if not collaborator:
            await self.close(code=4001)
            return

        if not await self._has_paid_access(collaborator.pharmacy_id):
            await self.close(code=WS_CLOSE_PAYMENT_REQUIRED)
            return

        self.pharmacy_id = collaborator.pharmacy_id
        self.room_group_name = f'sms_status_{self.pharmacy_id}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        # Échoter le sous-protocole offert par le client (['bearer', <jwt>]).
        await self.accept(subprotocol='bearer')

    @database_sync_to_async
    def _has_paid_access(self, pharmacy_id):
        return pharmacy_has_paid_access(pharmacy_id)

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Pas de receive() : le client n'envoie rien via WebSocket.

    async def sms_status_update(self, event):
        """Handler déclenché par group_send depuis le webhook OVH."""
        await self.send(text_data=json.dumps({
            'type': 'sms_status_update',
            'log_id': event['log_id'],
            'status': event['status'],
            'updated_at': event['updated_at'],
        }))
