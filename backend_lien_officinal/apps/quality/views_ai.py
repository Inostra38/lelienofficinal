import anthropic
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


def _get_client():
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY n'est pas configurée.")
    return anthropic.Anthropic(api_key=api_key)


CATEGORY_LABELS = {
    'dispensation': 'Dispensation',
    'hygiene': 'Hygiène',
    'stock': 'Stock',
    'administratif': 'Administratif',
    'autre': 'Autre',
}

SEVERITY_LABELS = {
    'minor': 'mineure',
    'major': 'majeure',
    'critical': 'critique',
}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_procedure_content(request):
    """
    Génère le contenu HTML d'une procédure à partir de ses métadonnées.
    Body: { title, category, reference, context? }
    """
    title = request.data.get('title', '').strip()
    category = request.data.get('category', '').strip()
    reference = request.data.get('reference', '').strip()
    context = request.data.get('context', '').strip()

    if not title or not category:
        return Response(
            {'error': 'Les champs title et category sont requis.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

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
        client = _get_client()
        message = client.messages.create(
            model='claude-opus-4-6',
            max_tokens=4096,
            thinking={'type': 'adaptive'},
            messages=[{'role': 'user', 'content': prompt}],
        )
        content = next(
            (block.text for block in message.content if block.type == 'text'),
            '',
        )
        return Response({'content': content})
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except anthropic.APIError as e:
        return Response(
            {'error': f'Erreur API Claude : {str(e)}'},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refactor_text(request):
    """
    Reformule ou améliore un texte de procédure avec Claude.
    Body: { text: str, mode: 'selection' | 'full' }
    """
    text = request.data.get('text', '').strip()
    mode = request.data.get('mode', 'full')

    if not text:
        return Response(
            {'error': 'Le champ text est requis.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    system_prompt = (
        "Tu es un assistant de rédaction pour des procédures pharmaceutiques officinales françaises. "
        "Corrige l'orthographe, améliore la clarté et structure le texte fourni. "
        "Ne modifie pas le sens ni le contenu médical. Ne génère pas de contenu nouveau. "
        "Réponds uniquement avec le texte corrigé, sans introduction ni commentaire. "
        "Si le texte est en HTML, conserve les balises HTML."
    )

    try:
        client = _get_client()
        message = client.messages.create(
            model='claude-opus-4-6',
            max_tokens=2048,
            system=system_prompt,
            messages=[{'role': 'user', 'content': text}],
        )
        result = next(
            (block.text for block in message.content if block.type == 'text'),
            '',
        )
        return Response({'result': result})
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except anthropic.APIError as e:
        return Response(
            {'error': f'Erreur API Claude : {str(e)}'},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def suggest_corrective_actions(request):
    """
    Suggère des actions correctives pour une non-conformité.
    Body: { nc_title, nc_description, severity }
    """
    nc_title = request.data.get('nc_title', '').strip()
    nc_description = request.data.get('nc_description', '').strip()
    severity = request.data.get('severity', '').strip()

    if not nc_title or not nc_description:
        return Response(
            {'error': 'Les champs nc_title et nc_description sont requis.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

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
        client = _get_client()
        message = client.messages.create(
            model='claude-opus-4-6',
            max_tokens=2048,
            thinking={'type': 'adaptive'},
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = next(
            (block.text for block in message.content if block.type == 'text'),
            '[]',
        )
        import json
        actions = json.loads(raw)
        return Response({'actions': actions})
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except (anthropic.APIError, json.JSONDecodeError) as e:
        return Response(
            {'error': f'Erreur lors de la génération : {str(e)}'},
            status=status.HTTP_502_BAD_GATEWAY,
        )
