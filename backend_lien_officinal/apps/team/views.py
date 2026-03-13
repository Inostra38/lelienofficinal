from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from .models import Collaborator
from .serializers import (
    CollaboratorSerializer,
    CollaboratorCreateSerializer,
    CollaboratorPermissionsSerializer,
    PinVerificationSerializer,
)
from apps.core.views import PinVerifyThrottle


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
    - Pas de session collaborateur → PIN du Titulaire (le mot de passe pharmacie
      est souvent partagé et ne constitue pas une preuve d'identité fiable)
    Retourne None si OK, sinon un Response d'erreur.
    """
    pin = request.data.get('confirmation_pin')
    if not pin:
        return Response({"detail": "PIN requis pour confirmer cette action."}, status=status.HTTP_403_FORBIDDEN)

    if collaborator:
        if not collaborator.check_pin(str(pin)):
            return Response({"detail": "PIN incorrect."}, status=status.HTTP_403_FORBIDDEN)
    else:
        # Connexion directe pharmacie → vérifier le PIN du Titulaire
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
    """
    Vérifie qu'un collaborateur a la permission requise.
    Si pas de collaborateur (pharmacie elle-même) → accès total.
    Retourne None si OK, sinon un Response d'erreur.
    """
    if collaborator and not getattr(collaborator, permission_name, False):
        return Response({"detail": "Permission insuffisante."}, status=status.HTTP_403_FORBIDDEN)
    return None


class CollaboratorViewSet(viewsets.ModelViewSet):
    """
    Vue pour gérer les collaborateurs de la pharmacie connectée.
    """
    serializer_class = CollaboratorSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_throttles(self):
        if self.action in ('collaborator_login', 'verify_pin', 'verify_team_pin'):
            return [PinVerifyThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        return Collaborator.objects.filter(pharmacy=self.request.user, is_active=True)

    def get_serializer_class(self):
        if self.action == 'create':
            return CollaboratorCreateSerializer
        return CollaboratorSerializer

    def perform_create(self, serializer):
        serializer.save(pharmacy=self.request.user)

    def create(self, request, *args, **kwargs):
        actor = _get_collaborator(request)

        err = _check_permission(actor, 'can_manage_team')
        if err:
            return err

        # Premier collaborateur : pas de confirmation requise (pharmacie déjà authentifiée via JWT)
        team_is_empty = not Collaborator.objects.filter(pharmacy=request.user, is_active=True).exists()
        if not (actor is None and team_is_empty):
            err = _verify_sensitive_action(request, actor)
            if err:
                return err

        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        actor = _get_collaborator(request)

        err = _check_permission(actor, 'can_manage_team')
        if err:
            return err

        # Interdire l'auto-suppression
        if actor and actor.id == instance.id:
            return Response({"detail": "Impossible de se supprimer soi-même."}, status=status.HTTP_403_FORBIDDEN)

        # Protéger le Titulaire
        if instance.role == Collaborator.Role.TITULAIRE:
            return Response({"detail": "Impossible de supprimer le Titulaire."}, status=status.HTTP_403_FORBIDDEN)

        err = _verify_sensitive_action(request, actor)
        if err:
            return err

        # Soft delete
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['patch'], url_path='permissions')
    def update_permissions(self, request, pk=None):
        """PATCH /api/team/{id}/permissions/ — modifier les droits d'un collaborateur"""
        instance = self.get_object()
        actor = _get_collaborator(request)

        err = _check_permission(actor, 'can_manage_team')
        if err:
            return err

        # Interdire l'auto-modification de permissions
        if actor and actor.id == instance.id:
            return Response({"detail": "Impossible de modifier ses propres permissions."}, status=status.HTTP_403_FORBIDDEN)

        # Protéger le Titulaire
        if instance.role == Collaborator.Role.TITULAIRE:
            return Response({"detail": "Les permissions du Titulaire ne peuvent pas être modifiées."}, status=status.HTTP_403_FORBIDDEN)

        err = _verify_sensitive_action(request, actor)
        if err:
            return err

        serializer = CollaboratorPermissionsSerializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            instance.refresh_from_db()
            return Response(CollaboratorSerializer(instance).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='login')
    def collaborator_login(self, request):
        """POST /api/team/login/ — échange un PIN contre un JWT collaborateur."""
        collaborator_id = request.data.get('collaborator_id')
        pin_code = request.data.get('pin_code')

        if not collaborator_id or not pin_code:
            return Response({"detail": "collaborator_id et pin_code requis."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            collaborator = Collaborator.objects.get(
                id=int(collaborator_id),
                pharmacy=request.user,
                is_active=True
            )
        except (Collaborator.DoesNotExist, ValueError):
            return Response({"detail": "Collaborateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if not collaborator.check_pin(str(pin_code)):
            return Response({"detail": "Code PIN incorrect."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(request.user)
        refresh['auth_type'] = 'collaborator'
        refresh['collaborator_id'] = collaborator.id

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'collaborator_id': collaborator.id,
        })

    @action(detail=False, methods=['post'], url_path='verify-team-pin')
    def verify_team_pin(self, request):
        """POST /api/team/verify-team-pin/ — vérifie le PIN avant une action de gestion."""
        actor = _get_collaborator(request)
        err = _verify_sensitive_action(request, actor)
        if err:
            return err
        return Response({"valid": True})

    @action(detail=False, methods=['post'], url_path='verify-pin')
    def verify_pin(self, request):
        """POST /api/team/verify-pin/ — valider un PIN collaborateur"""
        serializer = PinVerificationSerializer(data=request.data)
        if serializer.is_valid():
            collab_id = serializer.validated_data['collaborator_id']
            pin_code = serializer.validated_data['pin_code']

            try:
                collab = Collaborator.objects.get(id=collab_id, pharmacy=request.user)
            except Collaborator.DoesNotExist:
                return Response({"success": False, "message": "Collaborateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

            if collab.check_pin(pin_code):
                return Response({"success": True, "message": "PIN Valide"})
            else:
                return Response({"success": False, "message": "Code PIN incorrect"}, status=status.HTTP_403_FORBIDDEN)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
