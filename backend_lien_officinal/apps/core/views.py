from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Pharmacy
from .serializers import PharmacySerializer, PharmacyUpdateSerializer


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
