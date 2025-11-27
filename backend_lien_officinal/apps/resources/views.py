from rest_framework import viewsets, parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.filters import SearchFilter
from rest_framework.decorators import api_view, permission_classes, authentication_classes, action
from rest_framework.response import Response
from django.db.models import Prefetch, Q, Exists, OuterRef
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404

from .models import Category, ResourceCard, ResourceItem, PharmacyPreference 
from .serializers import (
    CategorySerializer, 
    CategoryCreateSerializer,
    ResourceCardSerializer, 
    ResourceItemSerializer, 
    CatalogCardSerializer
)


# =====================================================
# CATÉGORIES (CRUD COMPLET)
# =====================================================

@method_decorator(csrf_exempt, name='dispatch')
class CategoryViewSet(viewsets.ModelViewSet):
    """
    CRUD complet pour les catégories d'une pharmacie.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CategoryCreateSerializer
        return CategorySerializer

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

        # Cartes de l'utilisateur (PRIVATE uniquement maintenant)
        cards_qs_base = ResourceCard.objects.annotate(
            is_hidden_by_user=Exists(hidden_filter)
        ).exclude(is_hidden_by_user=True)

        items_filter = Q(owner__isnull=True) | Q(owner=user)
        
        native_cards_qs = cards_qs_base.prefetch_related(
            Prefetch('items', queryset=ResourceItem.objects.filter(items_filter).order_by('ordre', 'id'))
        ).filter(
            Q(type='PRIVATE', owner_pharmacy=user) |
            Q(type__in=['OFFICIAL', 'PARTNER'], category__isnull=False)
        )

        adopted_preferences = PharmacyPreference.objects.filter(
            pharmacy=user,
            assigned_category__isnull=False
        ).select_related('card', 'assigned_category')

        # Filtre par pharmacie propriétaire
        categories = Category.objects.filter(
            owner_pharmacy=user
        ).prefetch_related(
            Prefetch('cards', queryset=native_cards_qs),
            Prefetch('adopted_preferences', queryset=adopted_preferences)
        ).order_by('ordre')
        
        return categories

    def perform_create(self, serializer):
        """Associe automatiquement la catégorie à la pharmacie connectée."""
        last_order = Category.objects.filter(
            owner_pharmacy=self.request.user
        ).count()
        
        serializer.save(
            owner_pharmacy=self.request.user,
            ordre=last_order
        )

    def destroy(self, request, *args, **kwargs):
        """
        Suppression d'une catégorie.
        Les cartes PRIVATE sont supprimées en cascade (via on_delete=CASCADE).
        """
        category = self.get_object()
        
        if category.owner_pharmacy != request.user:
            return Response(
                {"detail": "Vous ne pouvez pas supprimer cette catégorie."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        category_name = category.nom
        cards_count = category.cards.count()
        
        category.delete()
        
        return Response({
            "detail": f"Catégorie '{category_name}' supprimée avec {cards_count} carte(s)."
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        """
        Réordonne les catégories en une seule requête.
        Attend un payload : { "order": [id1, id2, id3, ...] }
        """
        order = request.data.get('order', [])
        
        if not order:
            return Response(
                {"detail": "Le champ 'order' est requis."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mise à jour de l'ordre pour chaque catégorie
        for index, category_id in enumerate(order):
            Category.objects.filter(
                id=category_id,
                owner_pharmacy=request.user
            ).update(ordre=index)
        
        return Response({"detail": "Ordre mis à jour."}, status=status.HTTP_200_OK)


# =====================================================
# CARTES (CRUD pour cartes privées)
# =====================================================

@method_decorator(csrf_exempt, name='dispatch')
class ResourceCardViewSet(viewsets.ModelViewSet):
    serializer_class = ResourceCardSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        return ResourceCard.objects.filter(owner_pharmacy=self.request.user, type='PRIVATE')

    def perform_create(self, serializer):
        # Vérifier que la catégorie appartient à l'utilisateur
        category = serializer.validated_data.get('category')
        if category and category.owner_pharmacy != self.request.user:
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError({"category": "Cette catégorie ne vous appartient pas."})
        
        card = serializer.save(owner_pharmacy=self.request.user, type='PRIVATE')
        
        item_type = self.request.data.get('type', 'WEB')
        item_url = self.request.data.get('url', '')
        item_file = self.request.FILES.get('document')
        
        ResourceItem.objects.create(
            card=card,
            type=item_type,
            label=card.titre,
            url=item_url,
            file=item_file,
            owner=self.request.user,
            ordre=0
        )


# =====================================================
# ITEMS (CRUD)
# =====================================================

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


# =====================================================
# CATALOGUE (Lecture seule)
# =====================================================

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
# ADOPTION DE CARTE
# =====================================================

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def assign_category_to_card(request, pk):
    """
    Adopte une carte officielle/partenaire dans une catégorie personnelle.
    """
    card = get_object_or_404(ResourceCard, pk=pk)

    if card.type not in ['OFFICIAL', 'PARTNER']:
        return Response(
            {"detail": "Seules les cartes officielles peuvent être adoptées."}, 
            status=status.HTTP_403_FORBIDDEN
        )

    category_id = request.data.get('category')
    if not category_id:
        return Response(
            {"category": "Ce champ est obligatoire."}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    # Vérifier que la catégorie appartient à l'utilisateur
    category = get_object_or_404(Category, pk=category_id, owner_pharmacy=request.user)

    preference, created = PharmacyPreference.objects.get_or_create(
        pharmacy=request.user,
        card=card,
        defaults={'assigned_category': category}
    )
    
    if not created:
        preference.assigned_category = category
        preference.save()

    return Response({
        "detail": f"Carte '{card.titre}' adoptée dans la catégorie '{category.nom}'.",
        "card_id": card.id,
        "category_id": category.id,
        "category_nom": category.nom
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def toggle_favorite(request, pk):
    """
    Bascule le statut favori d'une carte pour la pharmacie connectée.
    Crée une PharmacyPreference si elle n'existe pas.
    """
    card = get_object_or_404(ResourceCard, pk=pk)

    # Récupérer ou créer la préférence
    preference, created = PharmacyPreference.objects.get_or_create(
        pharmacy=request.user,
        card=card,
        defaults={'is_favorite': True}
    )
    
    if not created:
        # Basculer l'état
        preference.is_favorite = not preference.is_favorite
        preference.save()

    return Response({
        "card_id": card.id,
        "is_favorite": preference.is_favorite
    }, status=status.HTTP_200_OK)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def update_notes(request, pk):
    """
    Met à jour les notes d'une carte pour la pharmacie connectée.
    """
    card = get_object_or_404(ResourceCard, pk=pk)

    # Récupérer ou créer la préférence
    preference, created = PharmacyPreference.objects.get_or_create(
        pharmacy=request.user,
        card=card
    )
    
    # Mettre à jour les notes si fournies
    if 'note_courte' in request.data:
        note_courte = request.data['note_courte'][:150]  # Limite à 150 caractères
        preference.note_courte = note_courte
    
    if 'note_longue' in request.data:
        preference.note_longue = request.data['note_longue']
    
    preference.save()

    return Response({
        "card_id": card.id,
        "note_courte": preference.note_courte,
        "note_longue": preference.note_longue
    }, status=status.HTTP_200_OK)