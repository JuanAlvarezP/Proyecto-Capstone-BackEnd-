from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView
)
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from projects.views import MeetingViewSet
from accounts.views import EmailTokenObtainPairView

@api_view(['GET'])
@permission_classes([AllowAny])
def storage_config_check(request):
    """Endpoint para verificar configuración de almacenamiento"""
    from django.core.files.storage import default_storage
    
    config_info = {
        'default_storage_class': str(default_storage.__class__.__name__),
        'default_storage_module': str(default_storage.__class__.__module__),
        'media_url': settings.MEDIA_URL,
        'use_cloudinary': getattr(settings, 'USE_CLOUDINARY', 'Not set'),
        'cloudinary_configured': bool(
            getattr(settings, 'CLOUDINARY_STORAGE', {}).get('CLOUD_NAME')
        ),
        'storages_config': getattr(settings, 'STORAGES', 'Not configured'),
        'default_file_storage': getattr(settings, 'DEFAULT_FILE_STORAGE', 'Not set'),
    }
    
    return Response(config_info)  

router = DefaultRouter()
router.register(r"meetings", MeetingViewSet, basename="meetings") 


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Diagnóstico de configuración
    path('api/storage-config/', storage_config_check, name='storage-config'),

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
