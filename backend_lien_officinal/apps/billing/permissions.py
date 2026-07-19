"""Séparation offre gratuite / modules payants.

Modèle commercial (décidé le 2026-07-19) :

- Le **tableau de bord est gratuit, définitivement et sans condition** :
  ressources, catégories, cartes, favoris, notes, préférences, profil de
  l'officine et gestion d'équipe. Aucune de ces vues ne doit porter
  ``HasPaidAccess``. Un test (test_free_tier.py) verrouille cette garantie.
- Les **modules payants** — planning, qualité, tâches, messagerie, SMS — sont
  ouverts pendant l'essai de 30 jours, puis exigent un abonnement actif.
- Un accès refusé ne bloque JAMAIS l'application : il renvoie 402 sur les seuls
  endpoints payants, et le titulaire retombe sur le tableau de bord gratuit.
"""

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission


class PaymentRequired(APIException):
    """402 — module payant hors offre gratuite.

    Volontairement distinct de 403 : le frontend doit proposer de s'abonner,
    et non traiter la réponse comme un défaut de droits.
    """

    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Ce module nécessite un abonnement actif."
    default_code = 'payment_required'


class HasPaidAccess(BasePermission):
    """Autorise les modules payants selon l'état de l'abonnement.

    À combiner avec ``IsAuthenticated`` — cette classe ne vérifie pas
    l'authentification.

    Une pharmacie **sans objet Subscription** est refusée : depuis le
    2026-07-19 l'inscription en crée un en période d'essai, donc son absence
    signale un compte antérieur, à traiter comme hors abonnement.
    """

    def has_permission(self, request, view):
        from apps.billing.models import Subscription

        # Requête explicite plutôt que getattr(pharmacy, 'subscription') :
        # l'accesseur inverse d'un OneToOne est mis en cache sur l'instance, et
        # renvoyait un abonnement périmé dès que request.user avait déjà été
        # touché dans le même cycle. Une lecture indexée sur une OneToOne est
        # peu coûteuse, et le droit d'accès ne doit pas dépendre d'un cache
        # d'ORM.
        subscription = Subscription.objects.filter(pharmacy=request.user).first()

        if subscription is None:
            raise PaymentRequired(detail="Aucun abonnement. Démarrez votre essai gratuit.")

        if not subscription.is_access_allowed:
            raise PaymentRequired(detail=_DENIAL_MESSAGES.get(
                subscription.access_denied_reason,
                PaymentRequired.default_detail,
            ))

        return True


def pharmacy_has_paid_access(pharmacy_id):
    """Version hors DRF, pour les consumers WebSocket.

    Les permissions DRF ne s'appliquent pas aux WebSockets : sans cette garde,
    messagerie, tâches et qualité resteraient accessibles en temps réel après
    expiration de l'abonnement, alors que leur API REST renvoie 402.

    Renvoie un booléen plutôt que de lever, les consumers fermant la connexion
    avec un code dédié (4402).
    """
    from apps.billing.models import Subscription

    subscription = Subscription.objects.filter(pharmacy_id=pharmacy_id).first()
    return subscription is not None and subscription.is_access_allowed


#: Code de fermeture WebSocket signalant un abonnement requis. Choisi dans la
#: plage privée 4000-4999, en écho au 402 de l'API REST.
WS_CLOSE_PAYMENT_REQUIRED = 4402


_DENIAL_MESSAGES = {
    'trial_expired':  "Votre essai gratuit est terminé. Abonnez-vous pour retrouver ce module.",
    'payment_failed': "Votre dernier paiement a échoué. Mettez à jour vos informations bancaires.",
    'suspended':      "Votre abonnement est suspendu pour impayé. Régularisez pour réactiver ce module.",
    'canceled':       "Votre abonnement est résilié. Réabonnez-vous pour retrouver ce module.",
}
