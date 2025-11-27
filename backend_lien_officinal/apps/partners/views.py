from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny  # ✅ Ajout
from rest_framework.response import Response
from .models import Partner
import random

@api_view(['GET'])
@permission_classes([AllowAny])  # ✅ Temporaire pour tester
def get_inactivity_ad(request):
    """
    Récupère une pub aléatoire pour l'overlay d'inactivité.
    """
    partners = Partner.objects.filter(
        inactivity_ad_active=True,
        inactivity_ad_image__isnull=False
    )
    
    if not partners.exists():
        return Response({"detail": "Aucune publicité disponible"}, status=404)
    
    # Sélection pondérée par priorité
    weights = [p.inactivity_ad_priority for p in partners]
    selected_partner = random.choices(list(partners), weights=weights, k=1)[0]
    
    ad_data = {
        "id": selected_partner.id,
        "image_url": request.build_absolute_uri(selected_partner.inactivity_ad_image.url),
        "link_url": selected_partner.inactivity_ad_link or "",
        "partner_name": selected_partner.nom,
    }
    
    return Response(ad_data)