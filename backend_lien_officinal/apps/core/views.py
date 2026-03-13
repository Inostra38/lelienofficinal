from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import Pharmacy
from .serializers import PharmacySerializer, PharmacyUpdateSerializer, RegisterSerializer, ProfileSetupSerializer
from apps.team.models import Collaborator


class PinVerifyThrottle(UserRateThrottle):
    """10 tentatives de PIN par 5 minutes par utilisateur authentifié."""
    scope = 'pin_verify'

    def get_rate(self):
        return '10/m'  # valeur factice — parse_rate impose la vraie limite

    def parse_rate(self, rate):
        return (10, 5 * 60)  # 10 requêtes par 300 secondes


def _get_collaborator(request):
    """Lit le collaborateur actif depuis le claim JWT (auth_type='collaborator')."""
    token = request.auth
    if not token:
        return None
    if token.get('auth_type') != 'collaborator':
        return None
    collab_id = token.get('collaborator_id')
    if not collab_id:
        return None
    try:
        return Collaborator.objects.get(id=int(collab_id), pharmacy=request.user, is_active=True)
    except (Collaborator.DoesNotExist, ValueError):
        return None


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


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            pharmacy = serializer.save()
            refresh = RefreshToken.for_user(pharmacy)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
        refresh_token_str = request.data.get('refresh_token', '')

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

        # Vérifier l'unicité
        if Pharmacy.objects.filter(email=new_email).exclude(id=request.user.id).exists():
            return Response({"new_email": "Cette adresse email est déjà utilisée."}, status=status.HTTP_400_BAD_REQUEST)

        # TODO (Mailgun): Stocker dans pending_email + générer token de vérification
        # request.user.pending_email = new_email
        # request.user.generate_email_verification_token()
        # Envoyer l'email de vérification via Mailgun
        # Pour l'instant : changement immédiat
        request.user.email = new_email
        request.user.save(update_fields=['email'])

        return Response({"detail": "Adresse email mise à jour avec succès.", "new_email": new_email})


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

        authorized = Collaborator.objects.filter(
            pharmacy=request.user,
            can_manage_account=True,
            is_active=True,
        )
        for collab in authorized:
            if collab.check_pin(str(pin)):
                return Response({"valid": True})

        return Response(
            {"detail": "PIN incorrect ou droits insuffisants."},
            status=status.HTTP_403_FORBIDDEN
        )
