"""
WebSocket consumer — IA qualité (génération de contenu, reformulation, actions correctives).

Protocole :
  Client → { "type": "refactor_text"|"suggest_actions",
              "request_id": "<uuid>", ...payload }
  Server → { "type": "result", "request_id": "<uuid>", "status": "success", ...data }
         | { "type": "error",  "request_id": "<uuid>", "message": "..." }

L'appel Anthropic est entièrement async — ne bloque pas Daphne.
"""
import json

import anthropic
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from apps.billing.permissions import (
    WS_CLOSE_PAYMENT_REQUIRED,
    pharmacy_has_paid_access,
)

from . import ai


class QualityAIConsumer(AsyncWebsocketConsumer):

    # ── Connexion / déconnexion ────────────────────────────────────────────

    async def connect(self):
        collaborator = self.scope.get('collaborator')
        if not collaborator:
            await self.close(code=4003)
            return
        if not await self._has_paid_access(collaborator.pharmacy_id):
            await self.close(code=WS_CLOSE_PAYMENT_REQUIRED)
            return
        self._anthropic = None
        # Échoter le sous-protocole offert par le client (['bearer', <jwt>]).
        await self.accept(subprotocol='bearer')

    @database_sync_to_async
    def _has_paid_access(self, pharmacy_id):
        return pharmacy_has_paid_access(pharmacy_id)

    async def disconnect(self, code):
        # Le client porte un pool de connexions HTTP : le fermer explicitement,
        # sinon il fuit pour toute la durée de vie du process Daphne.
        client, self._anthropic = getattr(self, '_anthropic', None), None
        if client is not None:
            await client.close()

    # ── Réception des messages ─────────────────────────────────────────────

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._error('', 'invalid_json', 'JSON invalide.')
            return

        msg_type   = data.get('type', '')
        request_id = data.get('request_id', '')

        handlers = {
            'refactor_text':   self._refactor_text,
            'suggest_actions': self._suggest_actions,
        }
        handler = handlers.get(msg_type)
        if not handler:
            await self._error(request_id, 'unknown_type', f'Type inconnu : {msg_type}')
            return

        await handler(data, request_id)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _client(self) -> anthropic.AsyncAnthropic:
        """Client partagé par toutes les requêtes de la connexion."""
        if getattr(self, '_anthropic', None) is None:
            api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY n'est pas configurée.")
            self._anthropic = anthropic.AsyncAnthropic(api_key=api_key)
        return self._anthropic

    async def _send(self, data: dict):
        await self.send(text_data=json.dumps(data))

    async def _error(self, request_id: str, code: str, message: str):
        await self._send({'type': 'error', 'request_id': request_id,
                          'code': code, 'message': message})

    async def _result(self, request_id: str, task_type: str, **kwargs):
        await self._send({'type': 'result', 'request_id': request_id,
                          'task_type': task_type, 'status': 'success', **kwargs})

    # ── Handlers ───────────────────────────────────────────────────────────

    async def _refactor_text(self, data: dict, request_id: str):
        text = data.get('text', '').strip()
        if not text:
            await self._error(request_id, 'validation', 'Le champ text est requis.')
            return

        try:
            message = await self._client().messages.create(
                **ai.build_refactor_text(text)
            )
            await self._result(request_id, 'refactor_text',
                               result=ai.extract_text(message))
        except Exception as e:
            await self._error(request_id, 'api_error', str(e))

    async def _suggest_actions(self, data: dict, request_id: str):
        nc_title       = data.get('nc_title', '').strip()
        nc_description = data.get('nc_description', '').strip()
        severity       = data.get('severity', '').strip()

        if not nc_title or not nc_description:
            await self._error(request_id, 'validation',
                              'Les champs nc_title et nc_description sont requis.')
            return

        try:
            message = await self._client().messages.create(
                **ai.build_corrective_actions(nc_title, nc_description, severity)
            )
            await self._result(request_id, 'suggest_actions',
                               actions=ai.extract_actions(message))
        except ai.TruncatedResponse as e:
            await self._error(request_id, 'parse_error', str(e))
        except Exception as e:
            await self._error(request_id, 'api_error', str(e))
