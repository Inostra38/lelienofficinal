# apps/partners/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Q03 : le pattern était une URL absolue collée dans path() → montée sous
    # 'api/', la route effective devenait /api/http://127.0.0.1:8000/api/ads/...
    # (injoignable). Route correcte : /api/ads/inactivity/.
    path('ads/inactivity/', views.get_inactivity_ad, name='inactivity-ad'),
]