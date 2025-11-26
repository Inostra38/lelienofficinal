from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from .models import Collaborator
from .serializers import CollaboratorSerializer, PinVerificationSerializer

class CollaboratorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Vue pour lister les collaborateurs de la pharmacie connectée.
    """
    serializer_class = CollaboratorSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication] # On s'assure que seul le Token est utilisé

    def get_queryset(self):
        # Filtre de sécurité : ne renvoie que les collaborateurs de la pharmacie connectée.
        return Collaborator.objects.filter(pharmacy=self.request.user, is_active=True)

    @action(detail=False, methods=['post'], url_path='verify-pin')
    def verify_pin(self, request):
        """
        Endpoint POST /api/team/verify-pin/ pour valider un PIN.
        """
        serializer = PinVerificationSerializer(data=request.data)
        if serializer.is_valid():
            collab_id = serializer.validated_data['collaborator_id']
            pin_code = serializer.validated_data['pin_code']

            # Récupère le collaborateur en vérifiant qu'il appartient bien à cette pharmacie
            try:
                collab = Collaborator.objects.get(id=collab_id, pharmacy=request.user)
            except Collaborator.DoesNotExist:
                return Response({"success": False, "message": "Collaborateur introuvable ou non autorisé."}, status=status.HTTP_404_NOT_FOUND)

            # Vérification du hash du PIN
            if collab.check_pin(pin_code):
                return Response({
                    "success": True, 
                    "message": "PIN Valide"
                })
            else:
                return Response({
                    "success": False, 
                    "message": "Code PIN incorrect"
                }, status=status.HTTP_403_FORBIDDEN)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)