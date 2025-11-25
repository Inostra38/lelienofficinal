from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Category
from .serializers import CategorySerializer

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API qui renvoie la liste des catégories AVEC leurs liens à l'intérieur.
    GET /api/categories/
    """
    queryset = Category.objects.all().order_by('ordre')
    serializer_class = CategorySerializer
    
    # Pour l'instant, on laisse public pour faciliter tes tests.
    # Plus tard, on mettra IsAuthenticated pour sécuriser.
    permission_classes = [AllowAny]