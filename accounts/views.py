from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from .serializers import (
    RegisterSerializer, MeSerializer, UserUpdateSerializer, 
    ChangePasswordSerializer, AdminUserSerializer, EmailTokenObtainPairSerializer
)


class EmailTokenObtainPairView(TokenObtainPairView):
    """
    Vista personalizada para obtener tokens JWT usando email en lugar de username.
    El frontend envía: { "email": "correo@ejemplo.com", "password": "..." }
    """
    serializer_class = EmailTokenObtainPairSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet para que los administradores gestionen usuarios.
    - GET /api/accounts/users/ - Listar todos los usuarios
    - POST /api/accounts/users/ - Crear nuevo usuario
    - GET /api/accounts/users/{id}/ - Ver detalle de un usuario
    - PUT/PATCH /api/accounts/users/{id}/ - Actualizar usuario
    - DELETE /api/accounts/users/{id}/ - Eliminar usuario
    """
    queryset = User.objects.all().order_by('-date_joined')
    permission_classes = [permissions.IsAdminUser]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return RegisterSerializer
        elif self.action in ['update', 'partial_update']:
            return AdminUserSerializer
        return MeSerializer


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer
    queryset = User.objects.all()

class MeView(generics.RetrieveAPIView):
    serializer_class = MeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user



class UpdateMeView(generics.UpdateAPIView):
    """
    Actualiza el perfil del usuario autenticado.
    URL: /accounts/me/update/  (ya definida en urls.py)
    Método: PUT o PATCH
    """
    serializer_class = UserUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # siempre operar sobre el usuario autenticado
        return self.request.user

class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["post"]

    def get_object(self):
        return self.request.user

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response({"detail": "La contraseña actual no es correcta."}, status=status.HTTP_400_BAD_REQUEST)
        user.setPassword(serializer.validated_data["new_password"]) if hasattr(user, "setPassword") else user.set_password(serializer.validated_data["new_password"])
        user.save()
        # Mantener la sesión activa tras el cambio
        try:
            update_session_auth_hash(request, user)
        except Exception:
            pass
        return Response({"ok": True})