#!/bin/bash
set -e

echo "🚀 Iniciando aplicación Django..."

# Esperar a que la base de datos esté lista (si se usa)
echo "⏳ Esperando a la base de datos..."
sleep 5

# Ejecutar migraciones
echo "📦 Ejecutando migraciones..."
python manage.py migrate --noinput

# Recolectar archivos estáticos
echo "📁 Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# Crear superusuario si no existe (opcional, para desarrollo)
if [ "$DJANGO_SUPERUSER_USERNAME" ] && [ "$DJANGO_SUPERUSER_EMAIL" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "👤 Creando superusuario..."
    python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
    print('✅ Superusuario creado')
else:
    print('ℹ️  Superusuario ya existe')
" || true
fi

echo "✅ Aplicación lista!"
echo "🌐 Servidor corriendo en http://0.0.0.0:8000"

# Ejecutar el comando pasado como argumentos
exec "$@"
