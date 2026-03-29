# backend_lien_officinal/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.core.serializers import PharmacyTokenObtainPairSerializer
from apps.core.views import health_check
from apps.core.views_media import serve_protected_media


class PharmacyTokenObtainPairView(TokenObtainPairView):
    serializer_class = PharmacyTokenObtainPairSerializer


urlpatterns = [
    path('admin/', admin.site.urls),

    # Monitoring
    path('api/health/', health_check, name='health_check'),

    # Fichiers media protégés par JWT (avant la route static Django)
    path('media/<path:path>', serve_protected_media, name='protected_media'),

    # API Routes
    path('api/', include('apps.core.urls')),
    path('api/', include('apps.resources.urls')),
    path('api/', include('apps.team.urls')),
    path('api/', include('apps.partners.urls')),
    path('api/', include('apps.messaging.urls')),
    path('api/', include('apps.tasks.urls')),
    path('api/', include('apps.planning.urls')),
    path('api/quality/', include('apps.quality.urls')),
    path('api/admin/', include('apps.admin_panel.urls')),

    # Auth
    path('api/token/', PharmacyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

# En développement, NE PAS ajouter static() pour /media/ :
# la route protected_media ci-dessus prend en charge toutes les requêtes /media/
# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)