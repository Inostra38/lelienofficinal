from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from django.utils import timezone
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




def _check_permission(collaborator, permission_name):
    """
    Vérifie qu'un collaborateur actif a la permission requise.
    Retourne None si OK, sinon un Response d'erreur.
    """
    if not collaborator:
        return Response({"detail": "Connexion collaborateur requise."}, status=status.HTTP_403_FORBIDDEN)
    if not getattr(collaborator, permission_name, False):
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
        if self.action in ('collaborator_login', 'verify_pin'):
            return [PinVerifyThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        include_archived = self.request.query_params.get('include_archived', 'false').lower() == 'true'
        qs = Collaborator.objects.filter(pharmacy=self.request.user).order_by('display_order', 'id')
        if not include_archived:
            qs = qs.filter(is_active=True)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return CollaboratorCreateSerializer
        return CollaboratorSerializer

    def perform_create(self, serializer):
        serializer.save(pharmacy=self.request.user)

    def create(self, request, *args, **kwargs):
        actor = _get_collaborator(request)
        
        # Exception Onboarding : Si l'équipe est vide, on autorise la création du premier collaborateur (Titulaire)
        # sans vérifier les permissions d'un acteur existant.
        team_is_empty = not Collaborator.objects.filter(pharmacy=request.user, is_active=True).exists()
        
        if not team_is_empty:
            err = _check_permission(actor, 'can_manage_team')
            if err:
                return err

        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        actor = _get_collaborator(request)

        err = _check_permission(actor, 'can_manage_team')
        if err:
            return err

        if actor and actor.id == instance.id:
            return Response({"detail": "Impossible de se supprimer soi-même."}, status=status.HTTP_403_FORBIDDEN)

        if instance.role == Collaborator.Role.TITULAIRE:
            return Response({"detail": "Impossible de supprimer le Titulaire."}, status=status.HTTP_403_FORBIDDEN)

        # Soft delete
        instance.is_active = False
        instance.archived_at = timezone.now()
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

        if actor and actor.id == instance.id:
            return Response({"detail": "Impossible de modifier ses propres permissions."}, status=status.HTTP_403_FORBIDDEN)

        if instance.role == Collaborator.Role.TITULAIRE:
            return Response({"detail": "Les permissions du Titulaire ne peuvent pas être modifiées."}, status=status.HTTP_403_FORBIDDEN)

        serializer = CollaboratorPermissionsSerializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            instance.refresh_from_db()
            return Response(CollaboratorSerializer(instance).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='reactivate')
    def reactivate(self, request, pk=None):
        """PATCH /api/team/{id}/reactivate/ — réactive un collaborateur archivé."""
        try:
            instance = Collaborator.objects.get(pk=pk, pharmacy=request.user)
        except Collaborator.DoesNotExist:
            return Response({"detail": "Collaborateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

        actor = _get_collaborator(request)
        err = _check_permission(actor, 'can_manage_team')
        if err:
            return err

        instance.is_active = True
        instance.archived_at = None
        instance.save()
        return Response(CollaboratorSerializer(instance).data)

    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        """POST /api/team/reorder/ — {"order": [id1, id2, ...]} — met à jour display_order."""
        order = request.data.get('order', [])
        if not isinstance(order, list):
            return Response({"detail": "order doit être une liste d'ids."}, status=status.HTTP_400_BAD_REQUEST)

        collaborators = Collaborator.objects.filter(pharmacy=request.user, is_active=True)
        collab_map = {c.id: c for c in collaborators}

        to_update = []
        for idx, collab_id in enumerate(order):
            collab = collab_map.get(int(collab_id))
            if collab:
                collab.display_order = idx
                to_update.append(collab)

        Collaborator.objects.bulk_update(to_update, ['display_order'])
        return Response({'ok': True})

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
        refresh['can_manage_quality'] = collaborator.can_manage_quality

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'collaborator_id': collaborator.id,
        })

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
