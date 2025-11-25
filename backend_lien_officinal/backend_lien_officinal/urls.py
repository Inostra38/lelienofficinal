from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # ✅ Les Catégories (Celle-ci marche déjà)
    path('api/', include('apps.resources.urls')),
    
    # 🚨 C'EST CETTE LIGNE QUI MANQUE CHEZ TOI :
    path('api/', include('apps.team.urls')), 
    
    # ✅ L'Authentification
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

# Gestion des images en mode Dev
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)