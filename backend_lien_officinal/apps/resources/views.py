from rest_framework import viewsets, parsers
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from .models import Category, Link
from .serializers import CategorySerializer, LinkSerializer

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all().order_by('ordre')
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

class LinkViewSet(viewsets.ModelViewSet):
    serializer_class = LinkSerializer
    permission_classes = [IsAuthenticated]
    
    # On accepte les fichiers (Multipart)
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous:
            return Link.objects.none()
        return Link.objects.filter(
            Q(is_public=True) | Q(pharmacy=user)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(pharmacy=self.request.user)