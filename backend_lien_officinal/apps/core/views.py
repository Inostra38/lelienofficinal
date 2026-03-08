from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Pharmacy
from .serializers import PharmacySerializer, PharmacyUpdateSerializer, RegisterSerializer, ProfileSetupSerializer


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
