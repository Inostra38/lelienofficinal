from rest_framework import viewsets, parsers, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.filters import SearchFilter
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from django.db.models import Prefetch, Q
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404

from .models import Category, ResourceCard, ResourceItem
from .serializers import CategorySerializer, ResourceCardSerializer, ResourceItemSerializer, CatalogCardSerializer

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lecture seule pour le Dashboard. Récupère les cartes et les items (Publics + Privés).
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        user = self.request.user
        if not user or user.is_anonymous:
            return Category.objects.none()

        # Filtre intelligent : Items Publics OU Items appartenant à l'utilisateur
        items_filter = Q(owner__isnull=True) | Q(owner=user)

        cards_qs = ResourceCard.objects.prefetch_related(
            Prefetch('items', queryset=ResourceItem.objects.filter(items_filter).order_by('ordre', 'id'))
        )
        
        return Category.objects.all().prefetch_related(
            Prefetch('cards', queryset=cards_qs)
        ).order_by('ordre')

@method_decorator(csrf_exempt, name='dispatch')
class ResourceCardViewSet(viewsets.ModelViewSet):
    """
    Gestion des cartes PRIVÉES (Création, Modification).
    """
    serializer_class = ResourceCardSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        # On ne liste que les cartes créées par la pharmacie connectée
        return ResourceCard.objects.filter(owner_pharmacy=self.request.user, type='PRIVATE')

    def perform_create(self, serializer):
        # Force le type et le propriétaire au moment de la création
        serializer.save(owner_pharmacy=self.request.user, type='PRIVATE')

@method_decorator(csrf_exempt, name='dispatch')
class ResourceItemViewSet(viewsets.ModelViewSet):
    """
    API pour ajouter/modifier/supprimer un Item (lien ou doc) dans une carte.
    """
    serializer_class = ResourceItemSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        # On ne liste que les items privés créés par l'utilisateur
        return ResourceItem.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        # On assigne le propriétaire au moment de la création
        serializer.save(owner=self.request.user)

class CatalogCardViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Liste les CARTES Officielles / Partenaires disponibles dans le catalogue pour adoption.
    """
    serializer_class = CatalogCardSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    filter_backends = [SearchFilter]
    search_fields = ['titre', 'description_officielle']

    def get_queryset(self):
        # On liste toutes les cartes Officielles ou Partenaires (qu'elles soient classées ou non)
        return ResourceCard.objects.filter(
            type__in=['OFFICIAL', 'PARTNER']
        ).order_by('titre')

# =================================================================
# VUE SPÉCIALISÉE POUR LE PATCH D'ASSIGNATION (Résout le bug 500)
# =================================================================

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def assign_category_to_card(request, pk):
    """
    Met à jour la catégorie d'une ResourceCard existante.
    Ceci résout l'erreur d'intégrité car on n'utilise pas le ViewSet générique pour cette action.
    """
    # 1. Tente de récupérer la carte
    card = get_object_or_404(ResourceCard, pk=pk)

    # 2. Sécurité : Vérifie que ce n'est pas une carte privée d'un autre utilisateur
    if card.owner_pharmacy and card.owner_pharmacy != request.user:
        return Response({"detail": "Cette carte est privée et ne peut être modifiée."}, status=status.HTTP_403_FORBIDDEN)
    
    # 3. Validation de la donnée
    category_id = request.data.get('category')
    if not category_id:
        return Response({"category": "Ce champ est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)

    # 4. Met à jour la carte (On utilise category_id, pas category)
    card.category_id = category_id
    card.save()

    # 5. Réponse
    serializer = ResourceCardSerializer(card)
    return Response(serializer.data)