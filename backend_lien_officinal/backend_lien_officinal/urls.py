from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # C'est ici qu'on branche nos APIs
    path('api/', include('apps.resources.urls')),
]

# Astuce pour servir les images (Logos) en mode Dev
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)