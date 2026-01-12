# serializers.py
from rest_framework import serializers
from .models import Application
from django.contrib.auth.models import User

class CandidateSerializer(serializers.ModelSerializer):
    """Serializer para mostrar información del candidato"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class ApplicationSerializer(serializers.ModelSerializer):
    # Para lectura: mostrar información completa del candidato
    candidate = CandidateSerializer(read_only=True)
    # Mantener el campo candidate_username por compatibilidad
    candidate_username = serializers.ReadOnlyField(source="candidate.username")
    # Información del proyecto (opcional pero útil)
    project_title = serializers.ReadOnlyField(source="project.title")

    class Meta:
        model = Application
        fields = "__all__"
        # El status ya no es read_only para que los admins puedan actualizarlo
        read_only_fields = ("candidate", "match_score", "parsed_text", "created_at","ai_analysis")
