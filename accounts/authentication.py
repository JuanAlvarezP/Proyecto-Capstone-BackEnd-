from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailBackend(ModelBackend):
    """
    Backend de autenticación personalizado que permite a los usuarios 
    iniciar sesión usando su email en lugar del username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        # El parámetro 'username' puede contener un email
        # También verificamos si se envió explícitamente 'email'
        email = kwargs.get('email', username)
        
        if email is None or password is None:
            return None
        
        try:
            # Buscar usuario por email
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Ejecutar el hash de contraseña para prevenir timing attacks
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # Si hay múltiples usuarios con el mismo email, buscar el primero activo
            user = User.objects.filter(email=email, is_active=True).first()
            if user is None:
                return None
        
        # Verificar la contraseña
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None
