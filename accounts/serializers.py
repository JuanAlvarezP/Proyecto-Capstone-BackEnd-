from django.contrib.auth.models import User
from rest_framework import serializers
import re

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    is_staff = serializers.BooleanField(required=False, default=False)
    is_superuser = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = User
        fields = ("username", "email", "password", "first_name", "last_name", "is_staff", "is_superuser")

    def validate_email(self, value):
        """
        Validar que el email no esté registrado
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Un usuario con este correo electrónico ya existe.")
        return value

    def validate_username(self, value):
        """
        Validar que el username no esté registrado
        """
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Este nombre de usuario ya está en uso.")
        return value

    def validate_password(self, value):
        """
        Validar que la contraseña cumpla con los estándares de seguridad:
        - Mínimo 8 caracteres
        - Al menos una letra mayúscula
        - Al menos una letra minúscula
        - Al menos un número
        - Al menos un carácter especial
        """
        if len(value) < 8:
            raise serializers.ValidationError(
                "La contraseña debe tener al menos 8 caracteres."
            )
        
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError(
                "La contraseña debe contener al menos una letra mayúscula."
            )
        
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError(
                "La contraseña debe contener al menos una letra minúscula."
            )
        
        if not re.search(r'\d', value):
            raise serializers.ValidationError(
                "La contraseña debe contener al menos un número."
            )
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError(
                "La contraseña debe contener al menos un carácter especial (!@#$%^&*(),.?\":{}|<>)."
            )
        
        # Validar que no contenga el username
        if hasattr(self, 'initial_data'):
            username = self.initial_data.get('username', '')
            if username and username.lower() in value.lower():
                raise serializers.ValidationError(
                    "La contraseña no debe contener el nombre de usuario."
                )
        
        return value

    def create(self, validated_data):
        # Extraer los campos de permisos
        is_staff = validated_data.pop('is_staff', False)
        is_superuser = validated_data.pop('is_superuser', False)
        
        # Extraer la contraseña
        password = validated_data.pop('password')
        
        # Crear el usuario sin contraseña primero
        user = User.objects.create(
            username=validated_data["username"],
            email=validated_data["email"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            is_staff=is_staff,
            is_superuser=is_superuser
        )
        
        # Establecer la contraseña de forma segura
        user.set_password(password)
        user.save()
        
        return user

class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "is_staff", "is_superuser", "first_name", "last_name")

 
class UpdateMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")
        extra_kwargs = {
            "email": {"required": False, "allow_blank": True},
            "first_name": {"required": False, "allow_blank": True},
            "last_name": {"required": False, "allow_blank": True},
        }

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)
    confirm_new_password = serializers.CharField(write_only=True, min_length=6)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_new_password"]:
            raise serializers.ValidationError("Las contraseñas nuevas no coinciden.")
        return attrs       
    

class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar el perfil del usuario autenticado."""
    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name"]
        extra_kwargs = {
            "email": {"required": False},
            "username": {"required": False},
            "first_name": {"required": False},
            "last_name": {"required": False},
        }

    def validate_email(self, value):
        user = self.context["request"].user
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError("Este email ya está en uso.")
        return value


class AdminUserSerializer(serializers.ModelSerializer):
    """Serializer para que administradores gestionen usuarios (incluyendo permisos)."""
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", 
                  "is_staff", "is_active", "is_superuser", "password", "date_joined"]
        read_only_fields = ["id", "date_joined"]
        extra_kwargs = {
            "email": {"required": False},
            "password": {"required": False}
        }
    
    def update(self, instance, validated_data):
        # Si se proporciona nueva contraseña, actualizarla
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        
        # Actualizar otros campos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance