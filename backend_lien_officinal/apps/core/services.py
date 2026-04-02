import re
import hashlib
import logging

logger = logging.getLogger(__name__)


class TemplateResolver:
    PHARMACY_VAR_MAP = {
        'pharmacie.nom': 'nom_officine',
        'pharmacie.ville': 'city',
        'pharmacie.adresse': 'address1',
        'pharmacie.adresse2': 'address2',
        'pharmacie.code_postal': 'postal_code',
        'pharmacie.region': 'region',
        'pharmacie.pays': 'country',
        'pharmacie.email': 'email',
        'pharmacie.telephone': 'phone',
    }

    EXPEDITEUR_VAR_MAP = {
        'expediteur.prenom': lambda c: c.first_name,
        'expediteur.nom': lambda c: c.last_name,
        'expediteur.prenom_nom': lambda c: (
            f"{c.first_name} {c.last_name[0]}." if c.last_name else c.first_name
        ),
        'expediteur.role': lambda c: c.role,
    }

    def resolve(self, content: str, pharmacy, custom_vars: dict = None,
                collaborator=None) -> dict:
        text = content
        custom_vars = custom_vars or {}

        # Passe 1 : variables pharmacie
        for var, field in self.PHARMACY_VAR_MAP.items():
            value = getattr(pharmacy, field, None)
            if value:
                text = text.replace('{{' + var + '}}', value)

        # Passe 2 : variables expéditeur (si un collaborateur est actif)
        if collaborator:
            for var, getter in self.EXPEDITEUR_VAR_MAP.items():
                try:
                    value = getter(collaborator)
                    if value:
                        text = text.replace('{{' + var + '}}', value)
                except Exception:
                    pass

        # Passe 3 : variables personnalisées fournies par le frontend
        for var, value in custom_vars.items():
            if value:
                text = text.replace('{{' + var + '}}', value)

        # Passe 4 : détection des variables non résolues
        missing = re.findall(r'\{\{([a-z_.]+)\}\}', text)

        return {
            'preview_text': text,
            'missing_vars': list(dict.fromkeys(missing)),
        }


class SMSPartnerService:
    BASE_URL = 'https://api.smspartner.fr/v1'

    def __init__(self):
        import requests
        from django.conf import settings
        self._requests = requests
        self.api_key = getattr(settings, 'SMSPARTNER_API_KEY', '')
        self.sender = getattr(settings, 'SMSPARTNER_SENDER', 'LienOfficinal')
        self.mock = not self.api_key
        if self.mock:
            logger.warning(
                "[SMS] MODE MOCK ACTIF — aucun SMS réel ne sera envoyé. "
                "Configurez SMSPARTNER_API_KEY en production."
            )

    @staticmethod
    def hash_phone(number: str) -> str:
        cleaned = ''.join(filter(str.isdigit, number))
        return hashlib.sha256(cleaned.encode()).hexdigest()

    @staticmethod
    def count_sms(text: str) -> int:
        gsm7 = set(
            '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ !"#¤%&\'()*+,-./'
            '0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            'ÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyz'
            'äöñüà^{}\\[~]|€'
        )
        is_gsm7 = all(c in gsm7 for c in text)
        limit1, limit_n = (160, 153) if is_gsm7 else (70, 67)
        length = len(text)
        if length <= limit1:
            return 1
        return (length + limit_n - 1) // limit_n

    @staticmethod
    def is_gsm7(text: str) -> bool:
        gsm7 = set(
            '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ !"#¤%&\'()*+,-./'
            '0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            'ÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyz'
            'äöñüà^{}\\[~]|€'
        )
        return all(c in gsm7 for c in text)

    def send_raw(self, to: str, message: str, webhook_url: str = '') -> str:
        """Appel SMS Partner — retourne le messageId (utilisé par la tâche Celery)."""
        if self.mock:
            import uuid
            return f'MOCK-{uuid.uuid4().hex[:8].upper()}'

        payload = {
            'apiKey': self.api_key,
            'phoneNumbers': to,
            'sender': self.sender,
            'gamme': 1,
            'message': message,
        }
        if webhook_url:
            payload['webhookUrl'] = webhook_url

        resp = self._requests.post(
            f'{self.BASE_URL}/send',
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get('success'):
            raise RuntimeError(f"SMS Partner error: {data}")
        return str(data.get('response', {}).get('messageId', ''))
