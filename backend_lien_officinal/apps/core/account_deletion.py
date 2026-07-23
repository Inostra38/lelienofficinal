"""
Suppression de compte — anonymisation RGPD.

On NE PEUT PAS faire ``pharmacy.delete()`` : les modèles de facturation
(``billing.Subscription/Invoice/SmsCreditTransaction/PromoRedemption``) pointent
vers ``Pharmacy`` en ``on_delete=PROTECT``, et les factures doivent être
conservées 10 ans (obligation comptable, art. L123-22 Code de commerce).

On efface donc toutes les données NON facturation, on conserve les factures,
et on **anonymise** la ligne pharmacie (la ligne survit comme ancre comptable).

Le seul PROTECT non-facturation du codebase est ``NonConformity.procedure →
Procedure`` (quality). On supprime donc les non-conformités d'abord, sinon le
balayage générique ne pourrait pas supprimer les procédures.
"""
import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Apps dont les données liées à la pharmacie sont CONSERVÉES (rétention légale).
KEEP_APP_LABELS = {'billing'}


@transaction.atomic
def execute_account_deletion(pharmacy_id: int) -> bool:
    """Efface les données non-facturation et anonymise la pharmacie.

    Idempotent : si la pharmacie est déjà anonymisée (ou inexistante), ne fait
    rien et renvoie ``False``. Renvoie ``True`` si l'anonymisation a été exécutée.
    """
    from apps.core.models import Pharmacy
    from apps.billing.models import SmsCreditTransaction

    try:
        pharmacy = Pharmacy.objects.select_for_update().get(pk=pharmacy_id)
    except Pharmacy.DoesNotExist:
        return False

    if pharmacy.anonymized_at:
        return False  # déjà anonymisée — idempotent

    logger.warning(
        "ACCOUNT DELETION EXEC — pharmacy_id=%s email=%s nom=%s",
        pharmacy.id, pharmacy.email, pharmacy.nom_officine,
    )

    # 1) Pré-suppression du seul PROTECT non-facturation : NonConformity protège
    #    Procedure. On retire les NC avant le balayage générique.
    from apps.quality.models import NonConformity
    NonConformity.objects.filter(pharmacy=pharmacy).delete()

    # 1b) Shift et AbsenceRequest n'ont pas de FK pharmacy directe : leur seul
    #     lien locataire est ``collaborator`` en ``on_delete=SET_NULL``. Le
    #     balayage générique (2) ne les atteint donc pas, et la suppression des
    #     collaborateurs les orphelinerait (collaborator=NULL) au lieu de les
    #     effacer — laissant en base des données RH sensibles (motifs d'absence
    #     dont « maladie », noms via ``collaborator_snapshot``) après
    #     l'anonymisation. On les supprime ici, tant que le lien existe encore.
    from apps.planning.models import Shift, AbsenceRequest
    Shift.objects.filter(collaborator__pharmacy=pharmacy).delete()
    AbsenceRequest.objects.filter(collaborator__pharmacy=pharmacy).delete()

    # 2) Balayage générique : supprime toutes les relations inverses (FK et O2O)
    #    NON facturation. On ignore les M2M inverses (supprimerait des objets
    #    partagés) et les apps conservées.
    for rel in pharmacy._meta.related_objects:
        if rel.many_to_many:
            continue
        if rel.related_model._meta.app_label in KEEP_APP_LABELS:
            continue
        accessor = rel.get_accessor_name()
        if rel.one_to_one:
            try:
                obj = getattr(pharmacy, accessor)
            except rel.related_model.DoesNotExist:
                continue
            if obj is not None:
                obj.delete()
        else:
            getattr(pharmacy, accessor).all().delete()

    # 3) Crédits SMS perdus — journalisés pour l'audit billing.
    credits = pharmacy.sms_credits
    if credits:
        SmsCreditTransaction.objects.create(
            pharmacy=pharmacy,
            delta=-credits,
            reason=SmsCreditTransaction.Reason.CLOSURE,
            note='Clôture du compte — crédits perdus',
        )

    # 3b) Effacement RGPD côté Stripe : supprimer le customer (PII : email, nom,
    #     IBAN/CB). Stripe conserve ses propres enregistrements financiers pour ses
    #     obligations légales. On n'échoue pas l'anonymisation si Stripe erre.
    from apps.billing.models import Subscription
    sub = Subscription.objects.filter(pharmacy=pharmacy).first()
    if sub and sub.stripe_customer_id:
        try:
            import stripe
            stripe.Customer.delete(sub.stripe_customer_id)
        except Exception:
            logger.exception(
                "Stripe customer delete failed during anonymization — pharmacy_id=%s",
                pharmacy.id,
            )

    # 4) Anonymisation de la pharmacie (la ligne survit pour les factures).
    pid = pharmacy.id
    pharmacy.email = f'deleted-{pid}@deleted.invalid'
    pharmacy.nom_officine = f'Pharmacie supprimée #{pid}'
    pharmacy.siret = None
    pharmacy.raison_sociale = ''
    pharmacy.vat_number = ''
    pharmacy.address1 = ''
    pharmacy.address2 = ''
    pharmacy.postal_code = ''
    pharmacy.city = ''
    pharmacy.region = ''
    pharmacy.phone_fixe = ''
    pharmacy.phone_mobile = ''
    pharmacy.pending_email = None
    pharmacy.email_verification_token = None
    pharmacy.email_verification_expires = None
    pharmacy.email_verified = False
    if pharmacy.logo:
        pharmacy.logo.delete(save=False)
    pharmacy.sms_credits = 0
    pharmacy.is_active = False
    pharmacy.onboarding_completed = False
    pharmacy.set_unusable_password()
    pharmacy.anonymized_at = timezone.now()
    pharmacy.save()

    return True
