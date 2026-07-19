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
        # Streaming imposé par le SDK au-delà de ~16k tokens de sortie, et
        # nécessaire ici : un planning 2 semaines mesuré dépasse déjà 16k une
        # fois le raisonnement compté dans le même budget.
        with client.messages.stream(
            model='claude-sonnet-5',
            max_tokens=32000,
            thinking={'type': 'adaptive'},
            system=system_prompt,
            messages=messages,
        ) as stream:
            ai_response = stream.get_final_message()

        # Le premier bloc est un bloc de raisonnement, pas du texte : sélectionner
        # explicitement le bloc textuel.
        assistant_message = next(
            (b.text for b in ai_response.content if b.type == 'text'), ''
        )

        if ai_response.stop_reason == 'max_tokens':
            logger.error('AI response truncated for task_id=%s', task_id)
            cache.set(cache_key, {
                'status': 'error',
                'detail': "La réponse de l'IA a été tronquée avant d'être complète. "
                          'Réessayez en réduisant le nombre de semaines demandées.',
            }, timeout=_TASK_TTL)
            return

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
