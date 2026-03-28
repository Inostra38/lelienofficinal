import json
import re
from datetime import date, timedelta
from decimal import Decimal


# ── Jours fériés français ──────────────────────────────────────────────────────

def get_jours_feries(year: int) -> list:
    """Jours fériés français (algorithme Meeus/Jones/Butcher pour Pâques)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    paques = date(year, month, day)
    return [
        date(year, 1, 1),
        paques + timedelta(days=1),   # Lundi de Pâques
        date(year, 5, 1),
        date(year, 5, 8),
        paques + timedelta(days=39),  # Ascension
        paques + timedelta(days=50),  # Lundi de Pentecôte
        date(year, 7, 14),
        date(year, 8, 15),
        date(year, 11, 1),
        date(year, 11, 11),
        date(year, 12, 25),
    ]


_LABELS_FERIES_FIXES = {
    (1, 1):   "Jour de l'An",
    (5, 1):   "Fête du Travail",
    (5, 8):   "Victoire 1945",
    (7, 14):  "Fête Nationale",
    (8, 15):  "Assomption",
    (11, 1):  "Toussaint",
    (11, 11): "Armistice",
    (12, 25): "Noël",
}


def get_label_ferie(d: date, year: int) -> str:
    label = _LABELS_FERIES_FIXES.get((d.month, d.day))
    if label:
        return label
    feries = get_jours_feries(year)
    paques_lundi = feries[1]
    paques = paques_lundi - timedelta(days=1)
    if d == paques_lundi:
        return "Lundi de Pâques"
    if d == paques + timedelta(days=39):
        return "Ascension"
    if d == paques + timedelta(days=50):
        return "Lundi de Pentecôte"
    return "Jour férié"


def compute_cp_days(
    start: date,
    end: date,
    start_period: str = 'morning',
    end_period: str = 'evening',
) -> Decimal:
    """
    Calcule le nombre de jours CP à déduire (CCN art. 13.2.c).
    Compte les jours lun–sam hors fériés français. Coupure fixe à 13h.

    Combinaisons :
      morning  → evening  = journées complètes        (ex : 5j)
      morning  → morning  = journées − 0,5j fin        (ex : 4,5j)
      afternoon → evening  = journées − 0,5j début     (ex : 4,5j)
      afternoon → morning  = journées − 1j (0,5+0,5)  (ex : 4j)
    """
    years = {start.year, end.year}
    feries: set[date] = set()
    for y in years:
        feries.update(get_jours_feries(y))

    working_days: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 6 and d not in feries:
            working_days.append(d)
        d += timedelta(days=1)

    total = Decimal(str(len(working_days)))

    if start_period == 'afternoon' and start in working_days:
        total -= Decimal('0.5')
    if end_period == 'morning' and end in working_days:
        total -= Decimal('0.5')

    return max(Decimal('0'), total)


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
