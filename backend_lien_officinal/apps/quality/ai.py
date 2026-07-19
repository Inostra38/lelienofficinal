"""
Configuration des appels Claude du module Qualité.

Prompts, modèle, effort et schémas de sortie vivent ici ; `consumers.py` ne
garde que le transport WebSocket et appelle `messages.create(**build_xxx(...))`.

L'effort est calibré par tâche : `refactor_text` est une réécriture bornée
déclenchée au clic, où la latence prime, tandis que les actions correctives
justifient un peu de raisonnement.
"""

MODEL = 'claude-sonnet-5'


class TruncatedResponse(Exception):
    """Réponse coupée par `max_tokens` avant d'être complète."""
    pass


SEVERITY_LABELS = {
    'minor':    'mineure',
    'major':    'majeure',
    'critical': 'critique',
}

DELAIS = ['immédiat', '1 semaine', '1 mois', '3 mois']


# ── Actions correctives : schéma de sortie ─────────────────────────────────────
# `output_config.format` garantit un JSON conforme : plus de balises markdown à
# décaper, plus de délai hors nomenclature, plus de JSONDecodeError à rattraper.

CORRECTIVE_ACTIONS_SCHEMA = {
    'type': 'json_schema',
    'schema': {
        'type': 'object',
        'properties': {
            'actions': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'description': {
                            'type': 'string',
                            'description': "L'action corrective à mener, formulée clairement.",
                        },
                        'delai': {
                            'type': 'string',
                            'enum': DELAIS,
                            'description': 'Le délai recommandé pour mener cette action.',
                        },
                    },
                    'required': ['description', 'delai'],
                    'additionalProperties': False,
                },
            },
        },
        'required': ['actions'],
        'additionalProperties': False,
    },
}


# ── Construction des requêtes ─────────────────────────────────────────────────

REFACTOR_SYSTEM_PROMPT = (
    "Tu es un assistant de rédaction pour des procédures pharmaceutiques officinales françaises. "
    "Corrige l'orthographe, améliore la clarté et structure le texte fourni. "
    "Ne modifie pas le sens ni le contenu médical. Ne génère pas de contenu nouveau. "
    "Réponds uniquement avec le texte corrigé, sans introduction ni commentaire. "
    "Si le texte est en HTML, conserve les balises HTML."
)


def build_refactor_text(text: str) -> dict:
    """Correction orthographique et mise au clair d'un texte existant."""
    return {
        'model': MODEL,
        'max_tokens': 4096,
        # Réécriture bornée, déclenchée au clic : le raisonnement n'apporte rien
        # et coûte en latence perçue.
        'thinking': {'type': 'disabled'},
        'output_config': {'effort': 'low'},
        'system': REFACTOR_SYSTEM_PROMPT,
        'messages': [{'role': 'user', 'content': text}],
    }


def build_corrective_actions(nc_title: str, nc_description: str, severity: str) -> dict:
    """Propositions d'actions correctives pour une non-conformité."""
    severity_label = SEVERITY_LABELS.get(severity, severity)
    prompt = f"""Tu es un expert en qualité pharmaceutique et gestion des non-conformités.

Une pharmacie d'officine a détecté la non-conformité suivante :
- Titre : {nc_title}
- Sévérité : {severity_label}
- Description : {nc_description}

Propose 3 à 5 actions correctives concrètes, réalistes et adaptées au contexte pharmaceutique.
Pour chaque action, indique une description claire de l'action à mener et le délai recommandé."""

    return {
        'model': MODEL,
        'max_tokens': 4096,
        'thinking': {'type': 'adaptive'},
        'output_config': {
            'effort': 'medium',
            'format': CORRECTIVE_ACTIONS_SCHEMA,
        },
        'messages': [{'role': 'user', 'content': prompt}],
    }


# ── Lecture des réponses ──────────────────────────────────────────────────────

def extract_text(message) -> str:
    """Premier bloc textuel de la réponse (ignore les blocs de raisonnement)."""
    return next(
        (block.text for block in message.content if block.type == 'text'), ''
    )


def extract_actions(message) -> list:
    """
    Actions correctives d'une réponse contrainte par CORRECTIVE_ACTIONS_SCHEMA.

    Le schéma garantit un JSON valide et conforme : seule une réponse tronquée
    (`stop_reason == 'max_tokens'`) peut encore produire du JSON incomplet.
    """
    import json

    if message.stop_reason == 'max_tokens':
        raise TruncatedResponse(
            "La réponse a été tronquée avant d'être complète. Réessayez avec une "
            'description de non-conformité plus courte.'
        )
    return json.loads(extract_text(message) or '{"actions": []}')['actions']
