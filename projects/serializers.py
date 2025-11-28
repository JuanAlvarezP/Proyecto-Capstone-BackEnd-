from rest_framework import serializers
from .models import Project, Meeting

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = "__all__"

class MeetingSerializer(serializers.ModelSerializer):
    project = ProjectSerializer(read_only=True)

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "client_name",
            "date",
            "created_by",
            "transcript_text",
            "hourly_rate",
            "ai_result",
            "project",
            "created_at",
        ]
        read_only_fields = ["created_by", "ai_result", "project", "created_at"]