from channels.generic.websocket import AsyncWebsocketConsumer


class TaskConsumer(AsyncWebsocketConsumer):
    """
    WebSocket en lecture seule : notifie les clients connectés
    quand une tâche est modifiée (create/update/delete/comment).
    Les mutations passent toujours par l'API REST ; ce canal
    sert uniquement à déclencher un refresh côté frontend.
    """

    async def connect(self):
        collaborator = self.scope.get('collaborator')
        if not collaborator:
            await self.close(code=4001)
            return

        self.pharmacy_id = collaborator.pharmacy_id
        self.room_group_name = f'tasks_pharmacy_{self.pharmacy_id}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        # Q09 : échoter le sous-protocole 'bearer' (comme le consumer messagerie).
        # Le client offre ['bearer', <jwt>] ; un navigateur exige que le serveur
        # confirme l'un des sous-protocoles offerts, sinon il rejette le handshake.
        await self.accept(subprotocol='bearer')

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Pas de receive() : le client n'envoie rien via WebSocket.

    async def task_update(self, event):
        """Handler déclenché par group_send depuis les views REST."""
        import json
        await self.send(text_data=json.dumps({'type': 'task_update'}))
