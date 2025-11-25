from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated # <--- CHANGEMENT
from .models import Category
from .serializers import CategorySerializer

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all().order_by('ordre')
    serializer_class = CategorySerializer
    
    # AVANT : permission_classes = [AllowAny]
    # MAINTENANT :
    permission_classes = [IsAuthenticated]