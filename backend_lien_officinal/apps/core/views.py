import json
import logging
import uuid

from datetime import timedelta
from django.conf import settings as _settings
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import PharmacyTokenObtainPairSerializer

logger = logging.getLogger(__name__)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import Pharmacy, PasswordResetToken
from .serializers import (
    PharmacySerializer, PharmacyUpdateSerializer, RegisterSerializer,
    ProfileSetupSerializer, ForgotPasswordSerializer, ResetPasswordSerializer,
)
from .auth_helpers import get_collaborator_from_jwt
from apps.team.models import Collaborator


class PinVerifyThrottle(UserRateThrottle):
    """10 tentatives de PIN par 5 minutes par utilisateur authentifié."""
    scope = 'pin_verify'

    def get_rate(self):
        return '10/m'  # valeur factice — parse_rate impose la vraie limite

    def parse_rate(self, rate):
        return (10, 5 * 60)  # 10 requêtes par 300 secondes


_get_collaborator = get_collaborator_from_jwt  # alias rétrocompat interne


def _verify_sensitive_action(request, collaborator):
    """
    Vérifie la confirmation de l'action sensible via PIN.
    - Collaborateur actif en session → son propre PIN
    - Pas de session collaborateur → PIN du Titulaire
    """
    pin = request.data.get('confirmation_pin')
    if not pin:
        return Response({"detail": "PIN requis pour confirmer cette action."}, status=status.HTTP_403_FORBIDDEN)

    if collaborator:
        if not collaborator.check_pin(str(pin)):
            return Response({"detail": "PIN incorrect."}, status=status.HTTP_403_FORBIDDEN)
    else:
        try:
            titulaire = Collaborator.objects.get(
                pharmacy=request.user,
                role=Collaborator.Role.TITULAIRE,
                is_active=True
            )
        except Collaborator.DoesNotExist:
            return Response(
                {"detail": "Aucun titulaire configuré. Veuillez d'abord créer un titulaire."},
                status=status.HTTP_403_FORBIDDEN
            )
        if not titulaire.check_pin(str(pin)):
            return Response({"detail": "PIN du titulaire incorrect."}, status=status.HTTP_403_FORBIDDEN)

    return None


def _check_permission(collaborator, permission_name):
    if collaborator and not getattr(collaborator, permission_name, False):
        return Response({"detail": "Permission insuffisante."}, status=status.HTTP_403_FORBIDDEN)
    return None


# ── Helpers cookies JWT ──────────────────────────────────────────────────────

def _cookie_kw(http_only=True):
    return dict(httponly=http_only, samesite='Strict', secure=not _settings.DEBUG, path='/')

def _refresh_max_age():
    return int(_settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())

def _build_session_info(auth_type='pharmacy_account', collaborator=None):
    data = {
        'auth_type': auth_type,
        'collaborator_id': None,
        'can_manage_account': False,
        'can_manage_team': False,
        'can_manage_planning': False,
        'can_manage_quality': False,
        'can_manage_procedures': False,
        'can_publish_procedures': False,
        'can_close_nonconformities': False,
        'can_assign_task': False,
    }
    if collaborator:
        data['collaborator_id'] = collaborator.id
        for field in [
            'can_manage_account', 'can_manage_team', 'can_manage_planning',
            'can_manage_quality', 'can_manage_procedures', 'can_publish_procedures',
            'can_close_nonconformities', 'can_assign_task',
        ]:
            data[field] = getattr(collaborator, field, False)
    return json.dumps(data, separators=(',', ':'))

def _set_refresh_cookie(response, refresh_str, clear_session=False):
    response.set_cookie('refresh_token', refresh_str, max_age=_refresh_max_age(), **_cookie_kw())
    if not clear_session:
        response.set_cookie(
            'session_info', _build_session_info(),
            max_age=_refresh_max_age(), **_cookie_kw(http_only=False),
        )

def _clear_auth_cookies(response):
    for name in ('refresh_token', 'session_info'):
        response.delete_cookie(name, path='/')


class RegisterRateThrottle(AnonRateThrottle):
    scope = 'register'


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            pharmacy = serializer.save()

            # Générer et envoyer le token de vérification email
            token = uuid.uuid4()
            pharmacy.email_verification_token = token
            pharmacy.email_verification_expires = timezone.now() + timedelta(hours=24)
            pharmacy.save(update_fields=['email_verification_token', 'email_verification_expires'])
            from apps.core.tasks import send_verification_email_task
            send_verification_email_task.delay(pharmacy.email, str(token))

            refresh = RefreshToken.for_user(pharmacy)
            response = Response({
                'access': str(refresh.access_token),
                'onboarding_completed': False,
                'email_verified': False,
            }, status=status.HTTP_201_CREATED)
            _set_refresh_cookie(response, str(refresh))
            return response
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginRateThrottle(AnonRateThrottle):
    """E3 : limite les tentatives de login pharmacie par IP (anti brute-force /
    credential stuffing). L'endpoint /api/token/ n'avait aucune limite."""
    scope = 'login'


class CookiePharmacyLoginView(TokenObtainPairView):
    """POST /api/token/ — Authentification pharmacie avec cookie refresh HttpOnly."""
    serializer_class = PharmacyTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            refresh_str = response.data.pop('refresh', None)
            if refresh_str:
                _set_refresh_cookie(response, refresh_str)
        return response


class ProfileSetupView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = ProfileSetupSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(PharmacySerializer(request.user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CompleteOnboardingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.onboarding_completed = True
        request.user.save(update_fields=['onboarding_completed'])
        return Response({'onboarding_completed': True})


class CookieTokenRefreshView(APIView):
    """POST /api/token/refresh/ — Refresh via cookie HttpOnly."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = request.COOKIES.get('refresh_token', '')
        if not raw:
            return Response({'detail': 'Refresh token manquant.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            token = RefreshToken(raw)
            new_access = str(token.access_token)
        except TokenError:
            return Response({'detail': 'Token invalide ou expiré.'}, status=status.HTTP_401_UNAUTHORIZED)

        response = Response({'access': new_access})
        # Mettre à jour session_info → toujours pharmacy_account après refresh
        response.set_cookie(
            'session_info', _build_session_info('pharmacy_account'),
            max_age=_refresh_max_age(), **_cookie_kw(http_only=False),
        )
        if _settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS'):
            response.set_cookie('refresh_token', str(token), max_age=_refresh_max_age(), **_cookie_kw())
        return response


class LogoutView(APIView):
    """POST /api/auth/logout/ — Invalide le refresh token et efface les cookies."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = request.COOKIES.get('refresh_token', '')
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_auth_cookies(response)
        return response


class CollabLogoutView(APIView):
    """POST /api/auth/collab-logout/ — Fin de session collaborateur, restaure session pharmacie."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.set_cookie(
            'session_info', _build_session_info('pharmacy_account'),
            max_age=_refresh_max_age(), **_cookie_kw(http_only=False),
        )
        return response


class PharmacyViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les informations de la pharmacie.
    Chaque pharmacie connectée ne peut voir/modifier que ses propres informations.
    """
    serializer_class = PharmacySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Retourne uniquement la pharmacie de l'utilisateur connecté"""
        return Pharmacy.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=['get'], url_path='me')
    def get_current_pharmacy(self, request):
        """Récupère les informations de la pharmacie connectée"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['put', 'patch'], url_path='me/update')
    def update_current_pharmacy(self, request):
        """Met à jour les informations de la pharmacie connectée"""
        serializer = PharmacyUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(PharmacySerializer(request.user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        actor = _get_collaborator(request)

        err = _check_permission(actor, 'can_manage_account')
        if err:
            return err

        err = _verify_sensitive_action(request, actor)
        if err:
            return err

        new_password = request.data.get('new_password', '')
        if len(new_password) < 8:
            return Response({"detail": "Le mot de passe doit faire au moins 8 caractères."}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_password)
        request.user.save()
        return Response({"detail": "Mot de passe modifié avec succès."})


class ChangeEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        actor = _get_collaborator(request)

        err = _check_permission(actor, 'can_manage_account')
        if err:
            return err

        err = _verify_sensitive_action(request, actor)
        if err:
            return err

        new_email = request.data.get('new_email', '').strip().lower()
        if not new_email or '@' not in new_email:
            return Response({"detail": "Adresse email invalide."}, status=status.HTTP_400_BAD_REQUEST)

        if Pharmacy.objects.filter(email=new_email).exclude(id=request.user.id).exists():
            return Response({"detail": "Cette adresse email est déjà utilisée."}, status=status.HTTP_400_BAD_REQUEST)

        request.user.email = new_email
        request.user.save(update_fields=['email'])
        return Response({"detail": "Email modifié avec succès.", "new_email": new_email})


# ── Endpoints /api/account/ (formulaires directs avec ancien mot de passe) ─────

class AccountChangePasswordView(APIView):
    """
    POST /api/account/change-password/
    Champs : old_password, new_password, new_password_confirm, refresh_token (optionnel)
    Après succès : blackliste le refresh token fourni → le client doit se reconnecter.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        actor = _get_collaborator(request)
        err = _check_permission(actor, 'can_manage_account')
        if err:
            return err

        old_password = request.data.get('old_password', '')
        new_password = request.data.get('new_password', '')
        new_password_confirm = request.data.get('new_password_confirm', '')
        refresh_token_str = request.COOKIES.get('refresh_token', '') or request.data.get('refresh_token', '')

        # Vérifier l'ancien mot de passe
        if not request.user.check_password(old_password):
            return Response({"old_password": "Mot de passe actuel incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier la correspondance
        if new_password != new_password_confirm:
            return Response({"new_password_confirm": "Les mots de passe ne correspondent pas."}, status=status.HTTP_400_BAD_REQUEST)

        # Appliquer les validateurs Django (longueur min, complexité, etc.)
        try:
            validate_password(new_password, request.user)
        except ValidationError as e:
            return Response({"new_password": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        # Changer le mot de passe
        request.user.set_password(new_password)
        request.user.save()

        # Blacklister le refresh token actuel si fourni
        if refresh_token_str:
            try:
                token = RefreshToken(refresh_token_str)
                token.blacklist()
            except TokenError:
                pass  # Token déjà invalide ou mal formé — on continue

        return Response({"detail": "Mot de passe modifié avec succès. Veuillez vous reconnecter."})


class AccountChangeEmailView(APIView):
    """
    POST /api/account/change-email/
    Champs : new_email, password (mot de passe actuel pour confirmer l'identité)

    TODO: Quand Mailgun sera configuré, envoyer un email de vérification à new_email
          avec le token, stocker dans pending_email et ne basculer qu'après vérification
          via GET /api/account/verify-email/?token=<uuid>
    Pour l'instant : changement immédiat, la structure pending_email/token est prête.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        actor = _get_collaborator(request)
        err = _check_permission(actor, 'can_manage_account')
        if err:
            return err

        new_email = request.data.get('new_email', '').strip().lower()
        password = request.data.get('password', '')

        # Vérifier le mot de passe pour confirmer l'identité
        if not request.user.check_password(password):
            return Response({"password": "Mot de passe incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        # Valider le format email
        if not new_email or '@' not in new_email or '.' not in new_email.split('@')[-1]:
            return Response({"new_email": "Adresse email invalide."}, status=status.HTTP_400_BAD_REQUEST)

        # Pas de changement si c'est le même email
        if new_email == request.user.email.lower():
            return Response({"new_email": "Ce nouvel email est identique à votre email actuel."}, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier l'unicité
        if Pharmacy.objects.filter(email=new_email).exclude(id=request.user.id).exists():
            return Response({"new_email": "Cette adresse email est déjà utilisée."}, status=status.HTTP_400_BAD_REQUEST)

        # Stocker le nouvel email en attente et envoyer la confirmation
        token = uuid.uuid4()
        request.user.pending_email = new_email
        request.user.email_verification_token = token
        request.user.email_verification_expires = timezone.now() + timedelta(hours=24)
        request.user.save(update_fields=['pending_email', 'email_verification_token', 'email_verification_expires'])

        from apps.core.tasks import send_email_change_task
        send_email_change_task.delay(request.user.email, new_email, str(token))

        return Response({"detail": f"Un lien de confirmation a été envoyé à {new_email}. Votre email actuel reste actif jusqu'à confirmation."})


class AccountVerifySecurityAccessView(APIView):
    """
    POST /api/account/verify-security-access/
    Accepte le PIN de n'importe quel collaborateur actif ayant can_manage_account=True.
    Indépendant du type de session JWT.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [PinVerifyThrottle]

    def post(self, request):
        pin = request.data.get('confirmation_pin')
        if not pin:
            return Response({"detail": "PIN requis."}, status=status.HTTP_403_FORBIDDEN)

        authorized = list(Collaborator.objects.filter(
            pharmacy=request.user,
            can_manage_account=True,
            is_active=True,
        ))
        # Parcourir TOUS les collaborateurs sans arrêt prématuré
        # pour éviter une fuite temporelle (timing attack).
        # check_pin utilise check_password (PBKDF2 constant-time),
        # mais une sortie anticipée rendrait le nombre d'itérations mesurable.
        matched = None
        for collab in authorized:
            if collab.check_pin(str(pin)):
                matched = collab  # ne pas break — continuer jusqu'au bout

        if matched is None:
            return Response(
                {"detail": "PIN incorrect ou droits insuffisants."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response({"valid": True})


class AccountDeleteView(APIView):
    """
    DELETE /api/account/delete/
    Programme la suppression du compte **en fin de période payée** (ou sous 30 j
    si aucun abonnement actif). Le compte reste utilisable jusqu'à l'échéance ;
    l'anonymisation effective est exécutée à ce moment (voir account_deletion.py).

    Réservé au **titulaire** : seules les sessions directes pharmacie (mot de passe)
    sont acceptées — les sessions collaborateur sont refusées.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [PinVerifyThrottle]

    def delete(self, request):
        pharmacy = request.user
        actor = _get_collaborator(request)

        # Titulaire uniquement : une session collaborateur ne peut pas supprimer.
        if actor is not None:
            return Response(
                {"detail": "Seul le titulaire du compte peut demander la suppression."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Ré-authentification par mot de passe (prouve l'identité du titulaire).
        password = request.data.get('password', '').strip()
        if not password:
            return Response(
                {"detail": "Le mot de passe est requis pour supprimer le compte."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not pharmacy.check_password(password):
            return Response(
                {"detail": "Mot de passe incorrect."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Déjà programmée ?
        if pharmacy.deletion_scheduled_for and not pharmacy.anonymized_at:
            return Response(
                {"detail": "Une suppression est déjà programmée.",
                 "deletion_scheduled_for": pharmacy.deletion_scheduled_for},
                status=status.HTTP_409_CONFLICT,
            )

        # Résilier l'abonnement Stripe en fin de période et caler l'échéance dessus.
        from apps.billing.models import Subscription
        from apps.billing.stripe_service import StripeService
        scheduled_for = None
        sub = Subscription.objects.filter(pharmacy=pharmacy).first()
        if sub and sub.stripe_subscription_id and sub.is_access_allowed:
            try:
                StripeService.cancel_subscription(sub.stripe_subscription_id)
                sub.cancel_at_period_end = True
                sub.save(update_fields=['cancel_at_period_end', 'updated_at'])
                scheduled_for = sub.current_period_end or sub.trial_ends_at
            except Exception:
                logger.exception(
                    "Stripe cancel failed during deletion request — pharmacy_id=%s",
                    pharmacy.id,
                )
        if scheduled_for is None:
            scheduled_for = timezone.now() + timedelta(days=30)

        pharmacy.deletion_requested_at = timezone.now()
        pharmacy.deletion_scheduled_for = scheduled_for
        pharmacy.save(update_fields=['deletion_requested_at', 'deletion_scheduled_for'])

        logger.warning(
            "ACCOUNT DELETION REQUESTED — pharmacy_id=%s email=%s scheduled_for=%s",
            pharmacy.id, pharmacy.email, scheduled_for,
        )
        # (email de confirmation + exécution à l'échéance : étape suivante)
        return Response(
            {"detail": "Suppression programmée.",
             "deletion_scheduled_for": scheduled_for},
            status=status.HTTP_200_OK,
        )


class CancelAccountDeletionView(APIView):
    """
    POST /api/account/delete/cancel/
    Annule une suppression programmée (réservé au titulaire) et reprend
    l'abonnement Stripe le cas échéant.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pharmacy = request.user
        actor = _get_collaborator(request)
        if actor is not None:
            return Response(
                {"detail": "Seul le titulaire du compte peut annuler la suppression."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not pharmacy.deletion_scheduled_for or pharmacy.anonymized_at:
            return Response(
                {"detail": "Aucune suppression programmée."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reprendre l'abonnement Stripe (annule le cancel_at_period_end).
        import stripe
        from apps.billing.models import Subscription
        sub = Subscription.objects.filter(pharmacy=pharmacy).first()
        if sub and sub.stripe_subscription_id and sub.cancel_at_period_end:
            try:
                stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=False)
                sub.cancel_at_period_end = False
                sub.save(update_fields=['cancel_at_period_end', 'updated_at'])
            except Exception:
                logger.exception(
                    "Stripe resume failed during deletion cancel — pharmacy_id=%s",
                    pharmacy.id,
                )

        pharmacy.deletion_requested_at = None
        pharmacy.deletion_scheduled_for = None
        pharmacy.save(update_fields=['deletion_requested_at', 'deletion_scheduled_for'])

        logger.warning("ACCOUNT DELETION CANCELLED — pharmacy_id=%s", pharmacy.id)
        return Response({"detail": "Suppression annulée."}, status=status.HTTP_200_OK)


# ── Health-check ──────────────────────────────────────────────────────────────

from django.http import JsonResponse
from django.db import connection as db_connection


def health_check(request):
    """
    GET /api/health/ — Pas d'authentification requise.
    Vérifie la connexion DB avant de répondre.
    """
    try:
        db_connection.ensure_connection()
        db_status = "ok"
    except Exception:
        db_status = "error"

    status_code = 200 if db_status == "ok" else 503
    return JsonResponse(
        {
            "status": "ok" if db_status == "ok" else "degraded",
            "db": db_status,
            "version": "1.0.0",
        },
        status=status_code,
    )


# ── Confirmation changement email ────────────────────────────────────────────

class ConfirmEmailChangeView(APIView):
    """POST /api/account/confirm-email-change/ — Bascule vers le nouvel email via token."""
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get("token", "").strip()
        if not token_str:
            return Response({"detail": "Token manquant."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token_uuid = uuid.UUID(token_str)
        except ValueError:
            return Response({"detail": "Token invalide."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pharmacy = Pharmacy.objects.get(email_verification_token=token_uuid, pending_email__gt='')
        except Pharmacy.DoesNotExist:
            return Response({"detail": "Lien invalide ou déjà utilisé."}, status=status.HTTP_400_BAD_REQUEST)

        if not pharmacy.email_verification_expires or timezone.now() > pharmacy.email_verification_expires:
            pharmacy.pending_email = ''
            pharmacy.email_verification_token = None
            pharmacy.email_verification_expires = None
            pharmacy.save(update_fields=['pending_email', 'email_verification_token', 'email_verification_expires'])
            return Response(
                {"detail": "Lien expiré. Votre ancien email a été conservé. Effectuez une nouvelle demande."},
                status=status.HTTP_400_BAD_REQUEST
            )

        pharmacy.email = pharmacy.pending_email
        pharmacy.pending_email = ''
        pharmacy.email_verification_token = None
        pharmacy.email_verification_expires = None
        pharmacy.email_verified = True
        pharmacy.save(update_fields=['email', 'pending_email', 'email_verification_token', 'email_verification_expires', 'email_verified'])

        return Response({"detail": "Votre email a été mis à jour avec succès."}, status=status.HTTP_200_OK)


class CancelEmailChangeView(APIView):
    """POST /api/account/cancel-email-change/ — Annule une demande de changement en cours."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pharmacy = request.user
        if not pharmacy.pending_email:
            return Response({"detail": "Aucune demande de changement en cours."}, status=status.HTTP_400_BAD_REQUEST)

        pharmacy.pending_email = ''
        pharmacy.email_verification_token = None
        pharmacy.email_verification_expires = None
        pharmacy.save(update_fields=['pending_email', 'email_verification_token', 'email_verification_expires'])

        return Response({"detail": "Demande de changement annulée."}, status=status.HTTP_200_OK)


# ── Vérification email ────────────────────────────────────────────────────────

class VerifyEmailView(APIView):
    """POST /api/auth/verify-email/ — Vérifie le token et marque email_verified=True."""
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get("token", "").strip()
        if not token_str:
            return Response({"detail": "Token manquant."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token_uuid = uuid.UUID(token_str)
        except ValueError:
            return Response({"detail": "Token invalide."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pharmacy = Pharmacy.objects.get(email_verification_token=token_uuid)
        except Pharmacy.DoesNotExist:
            return Response({"detail": "Token invalide ou déjà utilisé."}, status=status.HTTP_400_BAD_REQUEST)

        if pharmacy.email_verified:
            return Response({"detail": "Email déjà vérifié."}, status=status.HTTP_200_OK)

        if not pharmacy.email_verification_expires or timezone.now() > pharmacy.email_verification_expires:
            return Response(
                {"detail": "Lien expiré. Demandez un nouveau lien de vérification."},
                status=status.HTTP_400_BAD_REQUEST
            )

        pharmacy.email_verified = True
        pharmacy.email_verification_token = None
        pharmacy.email_verification_expires = None
        pharmacy.save(update_fields=["email_verified", "email_verification_token", "email_verification_expires"])

        return Response({"detail": "Email vérifié avec succès."}, status=status.HTTP_200_OK)


class ResendVerificationThrottle(UserRateThrottle):
    rate = '5/day'


class ResendVerificationEmailView(APIView):
    """POST /api/auth/resend-verification/ — Renvoie l'email de vérification."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ResendVerificationThrottle]

    def post(self, request):
        pharmacy = request.user

        if pharmacy.email_verified:
            return Response({"detail": "Email déjà vérifié."}, status=status.HTTP_200_OK)

        token = uuid.uuid4()
        pharmacy.email_verification_token = token
        pharmacy.email_verification_expires = timezone.now() + timedelta(hours=24)
        pharmacy.save(update_fields=["email_verification_token", "email_verification_expires"])

        from apps.core.tasks import send_verification_email_task
        send_verification_email_task.delay(pharmacy.email, str(token))

        return Response({"detail": "Email de vérification renvoyé."}, status=status.HTTP_200_OK)


class ForgotPasswordThrottle(AnonRateThrottle):
    rate = '5/hour'


class ForgotPasswordView(APIView):
    """POST /api/auth/forgot-password/ — Envoie un lien de réinitialisation."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ForgotPasswordThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            pharmacy = Pharmacy.objects.get(email=email)
            PasswordResetToken.objects.filter(pharmacy=pharmacy, used=False).update(used=True)
            reset_token = PasswordResetToken.objects.create(
                pharmacy=pharmacy,
                expires_at=timezone.now() + timedelta(hours=1),
            )
            from apps.core.tasks import send_password_reset_task
            send_password_reset_task.delay(pharmacy.email, str(reset_token.token))
        except Pharmacy.DoesNotExist:
            pass

        return Response(
            {"message": "Si cet email existe, un lien a été envoyé."},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    """POST /api/auth/reset-password/ — Réinitialise le mot de passe."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            reset_token = PasswordResetToken.objects.select_related('pharmacy').get(
                token=serializer.validated_data['token']
            )
        except PasswordResetToken.DoesNotExist:
            return Response(
                {"detail": "Ce lien est invalide ou a expiré."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not reset_token.is_valid():
            return Response(
                {"detail": "Ce lien est invalide ou a expiré."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_password = serializer.validated_data['password']
        try:
            validate_password(new_password, reset_token.pharmacy)
        except ValidationError as e:
            return Response({"detail": e.messages}, status=status.HTTP_400_BAD_REQUEST)

        reset_token.pharmacy.set_password(new_password)
        reset_token.pharmacy.save(update_fields=['password'])
        reset_token.used = True
        reset_token.save(update_fields=['used'])

        return Response(
            {"message": "Mot de passe mis à jour avec succès."},
            status=status.HTTP_200_OK,
        )
