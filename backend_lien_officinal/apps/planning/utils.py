import json
import re


class AIParseError(Exception):
    """Levée quand la réponse IA ne peut pas être interprétée comme un planning valide."""
    pass


_REQUIRED_SHIFT_FIELDS = ('collaborator_id', 'day_of_week', 'start_time', 'end_time')
_VALID_LETTERS = {'A', 'B', 'C', 'D'}


def _normalize_time(value: str) -> str:
    """'08:00' → '08:00:00',  '08:00:00' → '08:00:00'."""
    if len(value) == 5:
        return value + ':00'
    return value


def _extract_json_str(text: str) -> str:
    """
    Tente d'extraire une chaîne JSON depuis le texte brut de l'IA.
    Stratégie :
      1. Bloc ```json ... ```
      2. Bloc ``` ... ```
      3. Premier { ... } équilibré dans le texte
    Lève AIParseError si aucune de ces stratégies ne fonctionne.
    """
    # 1. ```json ... ```
    m = re.search(r'```json\s*([\s\S]*?)```', text)
    if m:
        return m.group(1).strip()

    # 2. ``` ... ``` (sans label)
    m = re.search(r'```\s*([\s\S]*?)```', text)
    if m:
        candidate = m.group(1).strip()
        if candidate.startswith('{'):
            return candidate

    # 3. Premier objet JSON brut équilibré
    start = text.find('{')
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]

    raise AIParseError("Aucun bloc JSON trouvé dans la réponse IA.")


def parse_ai_planning_response(text: str) -> dict:
    """
    Extrait et valide le planning JSON produit par l'IA.

    Retourne un dict {'weeks': {'A': [...], ...}, 'violations': [...]}
    Lève AIParseError si le JSON est absent, malformé, ou ne respecte pas la structure attendue.
    """
    json_str = _extract_json_str(text)

    # Correction des virgules traînantes que l'IA peut insérer (ex: [1, 2,])
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise AIParseError(f"JSON invalide : {exc}") from exc

    if not isinstance(data, dict):
        raise AIParseError("La réponse JSON doit être un objet (dict).")

    weeks = data.get('weeks')
    if not isinstance(weeks, dict) or not weeks:
        raise AIParseError("Clé 'weeks' manquante ou vide dans la réponse IA.")

    for letter, shifts in weeks.items():
        if letter not in _VALID_LETTERS:
            raise AIParseError(f"Lettre de semaine invalide : '{letter}'.")
        if not isinstance(shifts, list):
            raise AIParseError(f"La semaine '{letter}' doit être une liste de shifts.")
        for i, shift in enumerate(shifts):
            if not isinstance(shift, dict):
                raise AIParseError(f"Shift #{i} de la semaine '{letter}' doit être un objet.")
            for field in _REQUIRED_SHIFT_FIELDS:
                if field not in shift:
                    raise AIParseError(
                        f"Shift #{i} de la semaine '{letter}' : champ '{field}' manquant."
                    )
            # Normalisation des heures
            shift['start_time'] = _normalize_time(str(shift['start_time']))
            shift['end_time']   = _normalize_time(str(shift['end_time']))

    # Violations optionnelles — on s'assure que c'est une liste
    if 'violations' not in data or not isinstance(data['violations'], list):
        data['violations'] = []

    return data
