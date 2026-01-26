from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView
)
from rest_framework.routers import DefaultRouter
from projects.views import MeetingViewSet
from accounts.views import EmailTokenObtainPairView  

router = DefaultRouter()
router.register(r"meetings", MeetingViewSet, basename="meetings") 


urlpatterns = [
    path('admin/', admin.site.urls),

    # JWT endpoints - Usar vista personalizada para login con email
    path('api/auth/jwt/create/', EmailTokenObtainPairView.as_view(), name='jwt-create'),
    path('api/auth/jwt/refresh/', TokenRefreshView.as_view(), name='jwt-refresh'),
    path('api/auth/jwt/verify/', TokenVerifyView.as_view(), name='jwt-verify'),

    # Apps
    path('api/accounts/', include('accounts.urls')),
    path('api/projects/', include('projects.urls')),
    path('api/recruiting/', include('recruiting.urls')),
    path('api/assessments/', include('assessments.urls')),
]

# Servir archivos de medios tanto en desarrollo como en producción
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
