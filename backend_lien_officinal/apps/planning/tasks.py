import logging

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

_TASK_TTL = 600  # 10 minutes


@shared_task(name='planning.generate_template')
def generate_template_task(task_id: str, api_key: str, system_prompt: str, messages: list):
    """
    Appelle l'API Anthropic en arrière-plan et stocke le résultat en cache.
    Le frontend poll GET /api/planning/constraints/generate/<task_id>/ pour récupérer le résultat.
    """
    cache_key = f'ai_task:{task_id}'

    try:
        import anthropic as anthropic_sdk
        from .utils import parse_ai_planning_response, AIParseError

        client = anthropic_sdk.Anthropic(api_key=api_key)
        ai_response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=8000,
            system=system_prompt,
            messages=messages,
        )

        assistant_message = ai_response.content[0].text

        try:
            template_json = parse_ai_planning_response(assistant_message)
        except AIParseError as exc:
            logger.error('AI parse error: %s\nRaw: %s', exc, assistant_message)
            cache.set(cache_key, {
                'status': 'error',
                'detail': f"La réponse de l'IA n'a pas pu être interprétée : {exc}",
            }, timeout=_TASK_TTL)
            return

        # Reconstituer la conversation complète (messages = ceux envoyés sans l'assistant)
        conversation_out = list(messages) + [{'role': 'assistant', 'content': assistant_message}]

        cache.set(cache_key, {
            'status':       'done',
            'message':      assistant_message,
            'template':     template_json,
            'conversation': conversation_out,
        }, timeout=_TASK_TTL)

    except Exception as exc:
        logger.exception('generate_template_task failed for task_id=%s', task_id)
        cache.set(cache_key, {
            'status': 'error',
            'detail': 'Une erreur est survenue lors de la génération IA.',
        }, timeout=_TASK_TTL)
