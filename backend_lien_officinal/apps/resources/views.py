from rest_framework import viewsets, parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.filters import SearchFilter
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from django.db.models import Prefetch, Q, Exists, OuterRef
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404

from .models import Category, ResourceCard, ResourceItem, PharmacyPreference 
from .serializers import CategorySerializer, ResourceCardSerializer, ResourceItemSerializer, CatalogCardSerializer

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        user = self.request.user
        if not user or user.is_anonymous:
            return Category.objects.none()

        # Filtre pour les cartes cachées par l'utilisateur
        hidden_filter = PharmacyPreference.objects.filter(
            pharmacy=user,
            card=OuterRef('pk'),
            is_hidden=True
        )

        # =====================================================
        # PARTIE 1 : Cartes avec catégorie native (PRIVATE + OFFICIAL/PARTNER non adoptées)
        # =====================================================
        cards_qs_base = ResourceCard.objects.annotate(
            is_hidden_by_user=Exists(hidden_filter)
        ).exclude(is_hidden_by_user=True)

        items_filter = Q(owner__isnull=True) | Q(owner=user)
        
        # Cartes natives : PRIVATE de l'utilisateur OU OFFICIAL/PARTNER avec catégorie définie
        native_cards_qs = cards_qs_base.prefetch_related(
            Prefetch('items', queryset=ResourceItem.objects.filter(items_filter).order_by('ordre', 'id'))
        ).filter(
            Q(type='PRIVATE', owner_pharmacy=user) |  # Cartes privées de l'utilisateur
            Q(type__in=['OFFICIAL', 'PARTNER'], category__isnull=False)  # Officielles avec catégorie native
        )

        # =====================================================
        # PARTIE 2 : Cartes adoptées (OFFICIAL/PARTNER assignées par l'utilisateur)
        # =====================================================
        # On récupère les préférences avec une catégorie assignée
        adopted_preferences = PharmacyPreference.objects.filter(
            pharmacy=user,
            assigned_category__isnull=False
        ).select_related('card', 'assigned_category')

        # Construction du queryset des catégories avec les deux types de cartes
        categories = Category.objects.all().prefetch_related(
            Prefetch('cards', queryset=native_cards_qs),
            Prefetch('adopted_preferences', queryset=adopted_preferences)
        ).order_by('ordre')
        
        return categories

@method_decorator(csrf_exempt, name='dispatch')
class ResourceCardViewSet(viewsets.ModelViewSet):
    serializer_class = ResourceCardSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        return ResourceCard.objects.filter(owner_pharmacy=self.request.user, type='PRIVATE')

    def perform_create(self, serializer):
        # 1. Créer la carte (type='PRIVATE' forcé côté serveur)
        card = serializer.save(owner_pharmacy=self.request.user, type='PRIVATE')
        
        # 2. Récupérer les données pour le ResourceItem associé
        item_type = self.request.data.get('type', 'WEB')
        item_url = self.request.data.get('url', '')
        item_file = self.request.FILES.get('document')
        
        # 3. Créer automatiquement le premier ResourceItem lié à la carte
        ResourceItem.objects.create(
            card=card,
            type=item_type,
            label=card.titre,
            url=item_url,
            file=item_file,
            owner=self.request.user,
            ordre=0
        )

@method_decorator(csrf_exempt, name='dispatch')
class ResourceItemViewSet(viewsets.ModelViewSet):
    serializer_class = ResourceItemSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        return ResourceItem.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class CatalogCardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CatalogCardSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    filter_backends = [SearchFilter]
    search_fields = ['titre', 'description_officielle']

    def get_queryset(self):
        return ResourceCard.objects.filter(
            type__in=['OFFICIAL', 'PARTNER']
        ).order_by('titre')

# =====================================================
# ✅ NOUVELLE LOGIQUE D'ADOPTION
# =====================================================
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def assign_category_to_card(request, pk):
    """
    Adopte une carte officielle/partenaire dans une catégorie personnelle.
    Crée ou met à jour une PharmacyPreference avec la catégorie assignée.
    """
    card = get_object_or_404(ResourceCard, pk=pk)

    # Vérification : seules les cartes officielles/partenaires peuvent être adoptées
    if card.type not in ['OFFICIAL', 'PARTNER']:
        return Response(
            {"detail": "Seules les cartes officielles peuvent être adoptées."}, 
            status=status.HTTP_403_FORBIDDEN
        )

    # Récupération de la catégorie choisie
    category_id = request.data.get('category')
    if not category_id:
        return Response(
            {"category": "Ce champ est obligatoire."}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    # Vérifier que la catégorie existe
    category = get_object_or_404(Category, pk=category_id)

    # ✅ Créer ou mettre à jour la préférence utilisateur
    preference, created = PharmacyPreference.objects.get_or_create(
        pharmacy=request.user,
        card=card,
        defaults={'assigned_category': category}
    )
    
    if not created:
        # Mise à jour si la préférence existait déjà
        preference.assigned_category = category
        preference.save()

    return Response({
        "detail": f"Carte '{card.titre}' adoptée dans la catégorie '{category.nom}'.",
        "card_id": card.id,
        "category_id": category.id,
        "category_nom": category.nom
    }, status=status.HTTP_200_OK)