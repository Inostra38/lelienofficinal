from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Collaborator
from .serializers import CollaboratorSerializer, PinVerificationSerializer

class CollaboratorViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CollaboratorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # On ne renvoie que les collaborateurs de la pharmacie connectée
        return Collaborator.objects.filter(pharmacy=self.request.user, is_active=True)

    @action(detail=False, methods=['post'], url_path='verify-pin')
    def verify_pin(self, request):
        serializer = PinVerificationSerializer(data=request.data)
        if serializer.is_valid():
            collab_id = serializer.validated_data['collaborator_id']
            pin_code = serializer.validated_data['pin_code']

            # Vérification sécurisée
            collab = get_object_or_404(Collaborator, id=collab_id, pharmacy=request.user)

            if collab.check_pin(pin_code):
                return Response({"success": True, "message": "PIN Valide"})
            else:
                return Response({"success": False, "message": "Code incorrect"}, status=status.HTTP_403_FORBIDDEN)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)