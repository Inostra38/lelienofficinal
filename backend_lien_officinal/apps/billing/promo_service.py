import logging

from django.db import transaction

from apps.billing.models import PromoCode, PromoRedemption

logger = logging.getLogger(__name__)


class PromoError(Exception):
    """Erreur métier liée à un code promo."""
    pass


def validate_and_redeem(code: str, pharmacy) -> PromoCode:
    """
    Valide un code promo et l'applique à une pharmacie.

    - Vérifie existence, validité, non-expiration, quota global
    - Vérifie que la pharmacie ne l'a pas déjà utilisé
    - Incrémente current_uses de manière thread-safe (SELECT FOR UPDATE)
    - Crée le PromoRedemption

    Retourne le PromoCode si succès.
    Lève PromoError avec message lisible en cas d'échec.
    """
    try:
        promo = PromoCode.objects.get(code__iexact=code)
    except PromoCode.DoesNotExist:
        raise PromoError('Code promo invalide.')

    if not promo.is_valid():
        raise PromoError('Ce code promo n\'est plus disponible.')

    if PromoRedemption.objects.filter(promo_code=promo, pharmacy=pharmacy).exists():
        raise PromoError('Vous avez déjà utilisé ce code promo.')

    with transaction.atomic():
        # Verrou exclusif pour éviter le dépassement du quota en concurrence
        promo = PromoCode.objects.select_for_update().get(pk=promo.pk)

        # Revalide sous verrou
        if not promo.is_valid():
            raise PromoError('Ce code promo n\'est plus disponible.')

        promo.current_uses += 1
        promo.save(update_fields=['current_uses', 'updated_at'])

        PromoRedemption.objects.create(
            promo_code=promo,
            pharmacy=pharmacy,
        )

    logger.info(
        'Code promo appliqué : %s → pharmacy %s (%d mois offerts)',
        promo.code, pharmacy.id, promo.months_free
    )
    return promo


def get_pharmacy_promo(pharmacy) -> PromoCode | None:
    """Retourne le code promo utilisé par une pharmacie, ou None."""
    redemption = (
        PromoRedemption.objects
        .filter(pharmacy=pharmacy)
        .select_related('promo_code')
        .order_by('-redeemed_at')
        .first()
    )
    return redemption.promo_code if redemption else None
