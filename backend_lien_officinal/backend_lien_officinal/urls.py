from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Import des vues principales (pour l'authentification)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
# Assurez-vous d'avoir importé RegisterView si elle existe, sinon commentez-la
# from apps.core.views import RegisterView 

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Routes des applications
    path('api/', include('apps.resources.urls')),
    path('api/', include('apps.team.urls')),
    
    # Auth
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)