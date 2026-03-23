import re
import hashlib


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


class OVHService:
    def __init__(self):
        import ovh
        from django.conf import settings
        self.client = ovh.Client(
            endpoint=settings.OVH_ENDPOINT,
            application_key=settings.OVH_APP_KEY,
            application_secret=settings.OVH_APP_SECRET,
            consumer_key=settings.OVH_CONSUMER_KEY,
        )
        self.service_name = settings.OVH_SMS_SERVICE

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

    def send_raw(self, to: str, message: str) -> str:
        """Appel OVH brut — retourne l'ID du message OVH (utilisé par la tâche Celery)."""
        result = self.client.post(
            f'/sms/{self.service_name}/jobs',
            message=message,
            receivers=[to],
            senderForResponse=True,
            noStopClause=False,
        )
        ids = result.get('ids', []) if isinstance(result, dict) else []
        return ids[0] if ids else ''

    def send_sms(self, pharmacy, to: str, message: str,
                 template=None, recipient_civilite='', recipient_name='', motif=''):
        from apps.core.models import SMSLog
        credits_needed = self.count_sms(message)
        if pharmacy.sms_credits < credits_needed:
            raise ValueError(
                f"Crédits insuffisants : {credits_needed} requis, "
                f"{pharmacy.sms_credits} disponibles"
            )
        to_hash = self.hash_phone(to)
        try:
            self.client.post(
                f'/sms/{self.service_name}/jobs',
                message=message,
                receivers=[to],
                senderForResponse=True,
                noStopClause=False,
            )
            pharmacy.sms_credits -= credits_needed
            pharmacy.save(update_fields=['sms_credits'])
            SMSLog.objects.create(
                pharmacy=pharmacy,
                template=template,
                sent_by=pharmacy,
                to_hash=to_hash,
                recipient_civilite=recipient_civilite,
                recipient_name=recipient_name,
                motif=motif,
                status='SUCCESS',
                credits_used=credits_needed,
            )
        except Exception as e:
            SMSLog.objects.create(
                pharmacy=pharmacy,
                template=template,
                sent_by=pharmacy,
                to_hash=to_hash,
                recipient_civilite=recipient_civilite,
                recipient_name=recipient_name,
                motif=motif,
                status='FAILED',
                credits_used=0,
                error_message=str(e),
            )
            raise
