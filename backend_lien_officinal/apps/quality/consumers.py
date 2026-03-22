"""
WebSocket consumer — IA qualité (génération de contenu, reformulation, actions correctives).

Protocole :
  Client → { "type": "generate_content"|"refactor_text"|"suggest_actions",
              "request_id": "<uuid>", ...payload }
  Server → { "type": "result", "request_id": "<uuid>", "status": "success", ...data }
         | { "type": "error",  "request_id": "<uuid>", "message": "..." }

L'appel Anthropic est entièrement async — ne bloque pas Daphne.
"""
import json

import anthropic
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings


CATEGORY_LABELS = {
    'dispensation': 'Dispensation',
    'hygiene':      'Hygiène',
    'stock':        'Stock',
    'administratif': 'Administratif',
    'autre':        'Autre',
}

SEVERITY_LABELS = {
    'minor':    'mineure',
    'major':    'majeure',
    'critical': 'critique',
}


class QualityAIConsumer(AsyncWebsocketConsumer):

    # ── Connexion / déconnexion ────────────────────────────────────────────

    async def connect(self):
        collaborator = self.scope.get('collaborator')
        if not collaborator:
            await self.close(code=4003)
            return
        await self.accept()

    async def disconnect(self, code):
        pass

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
            'generate_content': self._generate_content,
            'refactor_text':    self._refactor_text,
            'suggest_actions':  self._suggest_actions,
        }
        handler = handlers.get(msg_type)
        if not handler:
            await self._error(request_id, 'unknown_type', f'Type inconnu : {msg_type}')
            return

        await handler(data, request_id)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _client(self) -> anthropic.AsyncAnthropic:
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY n'est pas configurée.")
        return anthropic.AsyncAnthropic(api_key=api_key)

    async def _send(self, data: dict):
        await self.send(text_data=json.dumps(data))

    async def _error(self, request_id: str, code: str, message: str):
        await self._send({'type': 'error', 'request_id': request_id,
                          'code': code, 'message': message})

    async def _result(self, request_id: str, task_type: str, **kwargs):
        await self._send({'type': 'result', 'request_id': request_id,
                          'task_type': task_type, 'status': 'success', **kwargs})

    @staticmethod
    def _extract_text(message) -> str:
        return next(
            (block.text for block in message.content if block.type == 'text'), ''
        )

    # ── Handlers ───────────────────────────────────────────────────────────

    async def _generate_content(self, data: dict, request_id: str):
        title     = data.get('title', '').strip()
        category  = data.get('category', '').strip()
        reference = data.get('reference', '').strip()
        context   = data.get('context', '').strip()

        if not title or not category:
            await self._error(request_id, 'validation',
                              'Les champs title et category sont requis.')
            return

        category_label = CATEGORY_LABELS.get(category, category)
        prompt = f"""Tu es un expert en qualité pharmaceutique.
Rédige le contenu complet d'une procédure opérationnelle standard (POS) pour une pharmacie d'officine.

Procédure :
- Référence : {reference}
- Titre : {title}
- Catégorie : {category_label}
{f'- Contexte supplémentaire : {context}' if context else ''}

Génère un contenu HTML structuré et professionnel avec :
1. Un objectif clair
2. Le domaine d'application
3. Les responsabilités
4. La procédure détaillée étape par étape (utilise <ol> ou <ul>)
5. Les documents associés / références réglementaires si pertinent

Utilise uniquement les balises HTML de base : <h2>, <h3>, <p>, <ul>, <ol>, <li>, <strong>, <em>.
Ne génère que le contenu HTML, sans balises <html>, <head> ou <body>.
Rédige en français, de manière professionnelle et précise."""

        try:
            message = await self._client().messages.create(
                model='claude-opus-4-6',
                max_tokens=4096,
                thinking={'type': 'adaptive'},
                messages=[{'role': 'user', 'content': prompt}],
            )
            await self._result(request_id, 'generate_content',
                               content=self._extract_text(message))
        except Exception as e:
            await self._error(request_id, 'api_error', str(e))

    async def _refactor_text(self, data: dict, request_id: str):
        text = data.get('text', '').strip()
        if not text:
            await self._error(request_id, 'validation', 'Le champ text est requis.')
            return

        system_prompt = (
            "Tu es un assistant de rédaction pour des procédures pharmaceutiques officinales françaises. "
            "Corrige l'orthographe, améliore la clarté et structure le texte fourni. "
            "Ne modifie pas le sens ni le contenu médical. Ne génère pas de contenu nouveau. "
            "Réponds uniquement avec le texte corrigé, sans introduction ni commentaire. "
            "Si le texte est en HTML, conserve les balises HTML."
        )

        try:
            message = await self._client().messages.create(
                model='claude-opus-4-6',
                max_tokens=2048,
                system=system_prompt,
                messages=[{'role': 'user', 'content': text}],
            )
            await self._result(request_id, 'refactor_text',
                               result=self._extract_text(message))
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

        severity_label = SEVERITY_LABELS.get(severity, severity)
        prompt = f"""Tu es un expert en qualité pharmaceutique et gestion des non-conformités.

Une pharmacie d'officine a détecté la non-conformité suivante :
- Titre : {nc_title}
- Sévérité : {severity_label}
- Description : {nc_description}

Propose 3 à 5 actions correctives concrètes, réalistes et adaptées au contexte pharmaceutique.
Pour chaque action, indique :
1. Une description claire de l'action à mener
2. Le délai recommandé (immédiat / 1 semaine / 1 mois / 3 mois)

Réponds uniquement avec un tableau JSON valide, sans markdown, sans texte avant ou après :
[
  {{"description": "...", "delai": "..."}},
  ...
]"""

        try:
            import json as _json
            message = await self._client().messages.create(
                model='claude-opus-4-6',
                max_tokens=2048,
                thinking={'type': 'adaptive'},
                messages=[{'role': 'user', 'content': prompt}],
            )
            raw     = self._extract_text(message) or '[]'
            actions = _json.loads(raw)
            await self._result(request_id, 'suggest_actions', actions=actions)
        except _json.JSONDecodeError:
            await self._error(request_id, 'parse_error',
                              'Réponse Claude non parseable en JSON.')
        except Exception as e:
            await self._error(request_id, 'api_error', str(e))
