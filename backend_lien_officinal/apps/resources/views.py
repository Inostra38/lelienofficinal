from rest_framework import viewsets, parsers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.filters import SearchFilter
from rest_framework.decorators import api_view, permission_classes, authentication_classes, action
from rest_framework.response import Response
from django.db.models import Prefetch, Q, Exists, OuterRef, Count
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from rest_framework import parsers

from .models import Category, ResourceCard, ResourceItem, PharmacyPreference, WizardCategory
from .serializers import (
    CategorySerializer, 
    CategoryCreateSerializer,
    ResourceCardSerializer, 
    ResourceItemSerializer, 
    CatalogCardSerializer
)


# =====================================================
# WIZARD ONBOARDING — 4 ENDPOINTS
# =====================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def wizard_categories(request):
    """
    Liste les catégories globales de la plateforme (sauf 'Autre').
    GET /api/wizard/categories/
    """
    categories = WizardCategory.objects.filter(is_active=True).exclude(nom='Autre')
    data = [{'id': c.id, 'nom': c.nom} for c in categories]
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def wizard_resources(request):
    """
    Liste toutes les ressources plateforme disponibles (OFFICIAL + PARTNER).
    GET /api/wizard/resources/
    """
    cards = ResourceCard.objects.filter(
        type__in=['OFFICIAL', 'PARTNER']
    ).order_by('titre')
    data = [
        {
            'id': c.id,
            'titre': c.titre,
            'description_officielle': c.description_officielle,
            'type': c.type,
        }
        for c in cards
    ]
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def wizard_classify(request):
    """
    Classifie les ressources sélectionnées dans les catégories choisies via Claude IA.
    POST /api/wizard/classify/
    Body: { "categories": [...], "resources": [{id, titre, description}, ...] }
    """
    import json
    import anthropic
    from django.conf import settings
    from apps.resources.models import WizardCategory

    selected_categories = request.data.get('categories', [])
    resources = request.data.get('resources', [])

    if not resources:
        return Response([])

    # Fallback : tout dans "Autre" si pas de catégories
    if not selected_categories:
        return Response([{'resource_id': r['id'], 'category': 'Autre'} for r in resources])

    # Enrichir les catégories avec leurs descriptions depuis la BDD
    cat_objects = WizardCategory.objects.filter(nom__in=selected_categories)
    cat_descriptions = {c.nom: c.description for c in cat_objects}

    categories_block = "\n".join(
        f'- {nom} : {cat_descriptions.get(nom, "")}'.strip(" :")
        for nom in selected_categories
    )

    resources_block = json.dumps(
        [{'id': r['id'], 'titre': r['titre'], 'description': r.get('description_officielle', '')} for r in resources],
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""Tu es un expert en pharmacie d'officine française chargé de classer des ressources professionnelles.

Une pharmacie a sélectionné les catégories suivantes pour organiser son espace de travail.
Chaque catégorie est accompagnée d'une description détaillée de ce qu'elle contient :

{categories_block}

Voici les ressources à classer :
{resources_block}

Consignes :
- Pour chaque ressource, choisis la catégorie la plus pertinente parmi celles listées ci-dessus.
- Base-toi sur le titre ET la description de la ressource, ainsi que sur la description de chaque catégorie.
- Si une ressource peut appartenir à plusieurs catégories, choisis celle qui correspond le mieux à son usage principal.
- Si vraiment aucune catégorie ne convient, utilise "Autre".
- Tu DOIS retourner une entrée pour CHAQUE ressource de la liste.

Réponds UNIQUEMENT avec un tableau JSON valide, sans texte avant ni après, sans balises markdown.
Format attendu :
[
  {{"resource_id": 1, "category": "Grossistes-répartiteurs"}},
  {{"resource_id": 2, "category": "Outils patients"}}
]"""

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=4096,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = message.content[0].text.strip()
        # Supprimer les balises markdown si présentes (```json ... ```)
        if raw.startswith('```'):
            raw = raw.split('```', 2)[1]
            if raw.startswith('json'):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
        return Response(result)
    except Exception:
        # Fallback silencieux : tout dans "Autre"
        return Response([{'resource_id': r['id'], 'category': 'Autre'} for r in resources])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def wizard_complete(request):
    """
    Sauvegarde complète du wizard en une transaction atomique.
    POST /api/wizard/complete/
    Body: {
      "pharmacy": { "nom_officine": "...", "city": "..." },
      "selected_categories": ["Grossistes-répartiteurs", ...],
      "classified_resources": [{"resource_id": 1, "category": "Grossistes-répartiteurs"}, ...],
      "collaborators": [{"first_name": "...", "last_name": "...", "role": "...", "pin": "..."}, ...]
    }
    """
    from django.db import transaction
    from apps.team.models import Collaborator

    pharmacy = request.user

    with transaction.atomic():
        # 1. Mettre à jour les champs de la pharmacie
        pharmacy_data = request.data.get('pharmacy', {})
        if pharmacy_data.get('nom_officine'):
            pharmacy.nom_officine = pharmacy_data['nom_officine']
        if pharmacy_data.get('city'):
            pharmacy.city = pharmacy_data['city']
        pharmacy.save()

        # 2. Créer les catégories pour la pharmacie
        selected_categories = request.data.get('selected_categories', [])
        category_map = {}  # nom → Category instance

        for index, nom in enumerate(selected_categories):
            cat, _ = Category.objects.get_or_create(
                owner_pharmacy=pharmacy,
                nom=nom,
                defaults={'ordre': index}
            )
            category_map[nom] = cat

        # Catégorie "Autre" systématique
        autre_cat, _ = Category.objects.get_or_create(
            owner_pharmacy=pharmacy,
            nom='Autre',
            defaults={'ordre': 999}
        )
        category_map['Autre'] = autre_cat

        # 3. Créer les PharmacyPreference pour les ressources classées
        classified_resources = request.data.get('classified_resources', [])
        for item in classified_resources:
            resource_id = item.get('resource_id')
            cat_nom = item.get('category', 'Autre')
            assigned_cat = category_map.get(cat_nom, autre_cat)

            try:
                # Seules les cartes partagées (OFFICIAL/PARTNER) sont adoptables,
                # comme dans assign_category_to_card. Sans ce filtre, un id de
                # carte PRIVATE d'une autre officine adopté ici la rendrait
                # lisible au dashboard de l'appelant (fuite inter-clients).
                card = ResourceCard.objects.get(
                    pk=resource_id, type__in=['OFFICIAL', 'PARTNER']
                )
                PharmacyPreference.objects.get_or_create(
                    pharmacy=pharmacy,
                    card=card,
                    defaults={'assigned_category': assigned_cat}
                )
            except ResourceCard.DoesNotExist:
                continue

        # 4. Créer les collaborateurs
        collaborators_data = request.data.get('collaborators', [])
        for collab_data in collaborators_data:
            first_name = collab_data.get('first_name', '').strip()
            last_name = collab_data.get('last_name', '').strip()
            role = collab_data.get('role', 'Préparateur')
            pin = collab_data.get('pin', '')

            if not first_name or not last_name:
                continue

            if not pin:
                continue

            collab, created = Collaborator.objects.get_or_create(
                pharmacy=pharmacy,
                first_name=first_name,
                last_name=last_name,
                defaults={
                    'role': role,
                    'pin_hash': '',
                    'is_active': True,
                }
            )
            if created or not collab.pin_hash:
                collab.set_pin(str(pin))
                collab.save()

        # 5. Marquer l'onboarding comme complété
        pharmacy.onboarding_completed = True
        pharmacy.save()

    return Response({'success': True})


# =====================================================
# ONBOARDING — INITIALISATION DES CATÉGORIES
# =====================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def init_categories(request):
    """
    Crée les catégories initiales choisies lors de l'onboarding.
    Attend : { "categories": [{"nom": "...", "icon_slug": "..."}, ...] }
    """
    categories_data = request.data.get('categories', [])

    if not categories_data:
        return Response(
            {'detail': 'Au moins une catégorie est requise.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    created = []
    for index, cat in enumerate(categories_data):
        nom = cat.get('nom', '').strip()
        if not nom:
            continue
        category = Category.objects.create(
            owner_pharmacy=request.user,
            nom=nom,
            ordre=index
        )
        created.append({'id': category.id, 'nom': category.nom})

    return Response({'created': created}, status=status.HTTP_201_CREATED)


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
            assigned_category__isnull=False,
            is_hidden=False
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
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]  # ✅ AJOUT JSONParser
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        return ResourceCard.objects.filter(owner_pharmacy=self.request.user, type='PRIVATE')

    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        """
        Réordonne les cartes et préférences adoptées dans une catégorie.
        Payload : { "items": [{"id": 1, "type": "PRIVATE", "ordre": 0}, ...] }
        """
        items_data = request.data.get('items', [])
        for item in items_data:
            card_id = item.get('id')
            ordre = item.get('ordre')
            card_type = item.get('type', 'PRIVATE')
            if card_id is None or ordre is None:
                continue
            if card_type == 'PRIVATE':
                ResourceCard.objects.filter(id=card_id, owner_pharmacy=request.user).update(ordre=ordre)
            else:
                PharmacyPreference.objects.filter(card_id=card_id, pharmacy=request.user).update(ordre=ordre)
        return Response({"detail": "Ordre mis à jour."}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        from rest_framework import serializers as drf_serializers
        from django.core.exceptions import ValidationError as DjangoValidationError
        from apps.core.upload_validation import (
            validate_upload, ALLOWED_IMAGE_TYPES, ALLOWED_IMAGE_EXTENSIONS,
        )

        # Vérifier que la catégorie appartient à l'utilisateur
        category = serializer.validated_data.get('category')
        if category and category.owner_pharmacy != self.request.user:
            raise drf_serializers.ValidationError({"category": "Cette catégorie ne vous appartient pas."})

        item_file = self.request.FILES.get('document')
        icon_file = self.request.FILES.get('icon')
        # M3 : valider type/taille avant toute création
        try:
            validate_upload(item_file)
            validate_upload(
                icon_file,
                allowed_types=ALLOWED_IMAGE_TYPES,
                allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
            )
        except DjangoValidationError as e:
            raise drf_serializers.ValidationError({"file": e.messages})

        card = serializer.save(owner_pharmacy=self.request.user, type='PRIVATE')

        item_type = self.request.data.get('type', 'WEB')
        item_url = self.request.data.get('url', '')

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
        # L'utilisateur ne voit que ses propres items privés
        return ResourceItem.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """
        Suppression sécurisée : seul le propriétaire peut supprimer.
        """
        item = self.get_object()
        
        # Vérifier que l'item appartient bien à l'utilisateur
        if item.owner != request.user:
            return Response(
                {"detail": "Vous ne pouvez pas supprimer cet item."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        item_label = item.label
        item.delete()
        
        return Response({
            "detail": f"Item '{item_label}' supprimé."
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        """
        Réordonne les items d'une carte.
        Attend un payload : { "items": [{"id": 1, "ordre": 0}, {"id": 2, "ordre": 1}] }
        """
        items_data = request.data.get('items', [])
        
        if not items_data:
            return Response(
                {"detail": "Le champ 'items' est requis."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mise à jour de l'ordre pour chaque item
        for item_data in items_data:
            item_id = item_data.get('id')
            new_ordre = item_data.get('ordre')
            
            if item_id is not None and new_ordre is not None:
                ResourceItem.objects.filter(
                    id=item_id,
                    owner=request.user  # Sécurité : seulement ses items
                ).update(ordre=new_ordre)
        
        return Response({"detail": "Ordre mis à jour."}, status=status.HTTP_200_OK)


# =====================================================
# CATALOGUE (Lecture seule)
# =====================================================

class CatalogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CatalogCardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CatalogCardSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    filter_backends = [SearchFilter]
    search_fields = ['titre', 'description_officielle']
    pagination_class = CatalogPagination

    def get_queryset(self):
        qs = ResourceCard.objects.filter(
            type__in=['OFFICIAL', 'PARTNER']
        ).annotate(
            pharmacy_count=Count('preferences', filter=Q(preferences__assigned_category__isnull=False), distinct=True)
        )
        type_filter = self.request.query_params.get('type')
        if type_filter in ['OFFICIAL', 'PARTNER']:
            qs = qs.filter(type=type_filter)
        return qs.order_by('-is_featured', 'titre')


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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def toggle_visibility(request, pk):
    """
    Masque une carte OFFICIAL/PARTNER pour la pharmacie connectée.
    Crée ou met à jour la PharmacyPreference avec is_hidden=True.
    Les cartes PRIVATE se suppriment via DELETE /api/cards/{id}/.
    """
    card = get_object_or_404(ResourceCard, pk=pk)

    if card.type == 'PRIVATE':
        return Response(
            {"detail": "Les ressources personnelles se suppriment via DELETE."},
            status=status.HTTP_400_BAD_REQUEST
        )

    preference, _ = PharmacyPreference.objects.get_or_create(
        pharmacy=request.user,
        card=card,
    )
    preference.is_hidden = True
    preference.save()

    return Response({"card_id": card.id, "is_hidden": True}, status=status.HTTP_200_OK)


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
        card=card,
        defaults={'note_courte': '', 'note_longue': ''}
    )

    # Mettre à jour les notes si fournies (null → "" pour éviter NOT NULL violation)
    if 'note_courte' in request.data:
        note_courte = (request.data['note_courte'] or '')[:150]
        preference.note_courte = note_courte

    if 'note_longue' in request.data:
        preference.note_longue = request.data['note_longue'] or ''
    
    preference.save()

    return Response({
        "card_id": card.id,
        "note_courte": preference.note_courte,
        "note_longue": preference.note_longue
    }, status=status.HTTP_200_OK)


# =====================================================
# RECOMMANDATION COMMUNAUTAIRE (côté pharmacien)
# =====================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def recommend_card(request, pk):
    """
    Recommande une carte PRIVATE à la communauté.
    POST /api/cards/<id>/recommend/
    """
    card = get_object_or_404(ResourceCard, pk=pk)

    if card.type != 'PRIVATE' or card.owner_pharmacy != request.user:
        return Response(
            {"detail": "Seules vos cartes privées peuvent être recommandées."},
            status=status.HTTP_403_FORBIDDEN
        )

    if card.recommended_to_community:
        return Response(
            {"detail": "Cette carte a déjà été recommandée.", "status": card.recommendation_status},
            status=status.HTTP_400_BAD_REQUEST
        )

    card.recommended_to_community = True
    card.recommended_by = request.user
    card.save()  # le signal pre_save remplit recommended_at et recommendation_status

    return Response({
        "detail": "Carte recommandée à la communauté.",
        "card_id": card.id,
        "recommendation_status": card.recommendation_status,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def recommend_item(request, pk):
    """
    Recommande un item personnel à la communauté.
    POST /api/items/<id>/recommend/
    Body optionnel : { "target_card_id": 123 }
    """
    item = get_object_or_404(ResourceItem, pk=pk)

    if item.owner != request.user:
        return Response(
            {"detail": "Seuls vos liens personnels peuvent être recommandés."},
            status=status.HTTP_403_FORBIDDEN
        )

    if item.recommended_to_community:
        return Response(
            {"detail": "Ce lien a déjà été recommandé.", "status": item.recommendation_status},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Carte OFFICIAL cible optionnelle
    target_card_id = request.data.get('target_card_id')
    if target_card_id:
        target_card = get_object_or_404(ResourceCard, pk=target_card_id, type='OFFICIAL')
        item.target_official_card = target_card

    item.recommended_to_community = True
    item.recommended_by = request.user
    item.save()  # le signal pre_save remplit recommended_at et recommendation_status

    return Response({
        "detail": "Lien recommandé à la communauté.",
        "item_id": item.id,
        "recommendation_status": item.recommendation_status,
    })


# =====================================================
# ✅ CRÉATION RESSOURCE COMPLÈTE
# =====================================================

@csrf_exempt  # ✅ Changé ici
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def create_full_card(request):
    """
    Crée une carte complète avec tous ses items, notes et logo en une seule requête.
    """
    try:
        # 1. Récupérer les données de base
        titre = request.data.get('titre')
        category_id = request.data.get('category')
        description_courte = request.data.get('description_courte', '')

        # Notes (null → "" pour éviter NOT NULL violation)
        note_courte = request.data.get('note_courte') or ''
        note_longue = request.data.get('note_longue') or ''
        
        # Items (JSON stringifié)
        items_json = request.data.get('items')
        
        if not titre or not category_id:
            return Response(
                {"error": "Titre et catégorie sont obligatoires"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier que la catégorie appartient à l'utilisateur
        category = get_object_or_404(Category, pk=category_id, owner_pharmacy=request.user)

        # M3 : valider type/taille de TOUS les fichiers avant toute création
        from django.core.exceptions import ValidationError as DjangoValidationError
        from apps.core.upload_validation import validate_upload
        for uploaded in request.FILES.values():
            try:
                validate_upload(uploaded)
            except DjangoValidationError as e:
                return Response({"error": e.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Créer la carte
        card = ResourceCard.objects.create(
            titre=titre,
            category=category,
            description_officielle=description_courte,
            owner_pharmacy=request.user,
            type='PRIVATE'
        )
        
        # 3. Créer les items
        if items_json:
            import json
            items_data = json.loads(items_json)
            
            for index, item_data in enumerate(items_data):
                item_type = item_data.get('type')
                label = item_data.get('label')
                url = item_data.get('url', '')
                ordre = item_data.get('ordre', index)
                
                # Récupérer le fichier associé si présent
                file_key = f'item_file_{index}'
                file = request.FILES.get(file_key)
                
                ResourceItem.objects.create(
                    card=card,
                    type=item_type,
                    label=label,
                    url=url,
                    file=file,
                    owner=request.user,
                    ordre=ordre
                )
        
        # 4. Créer/Mettre à jour les préférences (notes)
        if note_courte or note_longue:
            PharmacyPreference.objects.update_or_create(
                pharmacy=request.user,
                card=card,
                defaults={
                    'note_courte': note_courte,
                    'note_longue': note_longue
                }
            )
        
        return Response({
            "id": card.id,
            "titre": card.titre,
            "message": "Ressource créée avec succès"
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        import traceback
        print("❌ Erreur complète:", traceback.format_exc())  # Pour le debug
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )