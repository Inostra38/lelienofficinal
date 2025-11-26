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
    """
    Vue principale pour le Dashboard. Filtre les cartes masquées par l'utilisateur.
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        user = self.request.user
        if not user or user.is_anonymous:
            return Category.objects.none()

        # 1. Filtre les cartes masquées par l'utilisateur connecté
        hidden_filter = PharmacyPreference.objects.filter(
            pharmacy=user,
            card=OuterRef('pk'),
            is_hidden=True
        )

        cards_qs_base = ResourceCard.objects.annotate(
            is_hidden_by_user=Exists(hidden_filter)
        ).exclude(is_hidden_by_user=True)

        # 2. Prépare les items (Publics OU Privés de l'utilisateur)
        items_filter = Q(owner__isnull=True) | Q(owner=user)
        
        # 3. Finalisation de la QuerySet
        cards_qs = cards_qs_base.prefetch_related(
            Prefetch('items', queryset=ResourceItem.objects.filter(items_filter).order_by('ordre', 'id'))
        ).filter(
            # Affiche les cartes Officielles/Partenaires non masquées OU les cartes Privées de l'utilisateur
            Q(type__in=['OFFICIAL', 'PARTNER']) | Q(owner_pharmacy=user)
        )
        
        return Category.objects.all().prefetch_related(
            Prefetch('cards', queryset=cards_qs)
        ).order_by('ordre')

@method_decorator(csrf_exempt, name='dispatch')
class ResourceCardViewSet(viewsets.ModelViewSet):
    """
    Gestion des cartes PRIVÉES (création/suppression).
    """
    serializer_class = ResourceCardSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        # Ne liste que les cartes créées par la pharmacie connectée
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
        # Ne liste que les items privés créés par l'utilisateur
        return ResourceItem.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        # Assigne le propriétaire au moment de la création
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
        # Liste toutes les cartes Officielles ou Partenaires disponibles pour être adoptées
        return ResourceCard.objects.filter(
            type__in=['OFFICIAL', 'PARTNER']
        ).order_by('titre')

# =================================================================
# VUE SPÉCIALISÉE POUR LE PATCH D'ASSIGNATION (Résout le bug d'assignation)
# =================================================================

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def assign_category_to_card(request, pk):
    """
    Met à jour la catégorie d'une ResourceCard existante et l'assigne à la pharmacie.
    Ceci est la solution chirurgicale pour l'adoption du catalogue.
    """
    card = get_object_or_404(ResourceCard, pk=pk)

    # 1. Sécurité : Seules les cartes officielles/partenaires peuvent être adoptées
    if card.type not in ['OFFICIAL', 'PARTNER']:
        return Response({"detail": "Seules les cartes officielles peuvent être adoptées."}, status=status.HTTP_403_FORBIDDEN)

    category_id = request.data.get('category')
    if not category_id:
        return Response({"category": "Ce champ est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)

    # 2. Mise à jour de la carte :
    card.category_id = category_id
    card.owner_pharmacy = request.user # 👈 ASSIGNATION DE LA PROPRIÉTÉ
    card.save()

    # 3. Réponse avec la carte mise à jour
    serializer = ResourceCardSerializer(card)
    return Response(serializer.data)

# =================================================================
# VUE SPÉCIALISÉE POUR LE TOGGLE DE VISIBILITÉ (Ajouté pour le masquage)
# =================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def toggle_card_visibility(request, pk):
    """
    Bascule l'état is_hidden pour la carte et l'utilisateur connecté.
    C'est la solution sécurisée pour "Masquer" une carte officielle/partenaire.
    """
    card = get_object_or_404(ResourceCard, pk=pk)
    
    # 1. Sécurité : S'assurer que la carte peut être masquée
    if card.type not in ['OFFICIAL', 'PARTNER']:
        return Response({"detail": "Seules les cartes officielles peuvent être masquées."}, status=status.HTTP_403_FORBIDDEN)
    
    # 2. Récupère ou crée la préférence de l'utilisateur pour cette carte
    preference, created = PharmacyPreference.objects.get_or_create(
        pharmacy=request.user,
        card=card,
        defaults={'is_hidden': True} 
    )

    if not created:
        # 3. Si la préférence existait, on inverse la visibilité
        preference.is_hidden = not preference.is_hidden
        preference.save()

    return Response({"is_hidden": preference.is_hidden, "action": "updated" if not created else "hidden"})