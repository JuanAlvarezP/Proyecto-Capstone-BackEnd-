from rest_framework import viewsets, permissions,mixins, status
from .models import Project,Meeting
from .serializers import ProjectSerializer,MeetingSerializer
from recruiting.ai_client import analyze_meeting_transcript
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by("-id")
    serializer_class = ProjectSerializer

 


class MeetingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    queryset = Meeting.objects.all()
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def create(self, request, *args, **kwargs):
        """
        Crea la reunión + proyecto usando el transcript y la IA.
        """
        title = request.data.get("title", "Proyecto desde reunión")
        client = request.data.get("client_name", "")
        hourly_rate = request.data.get("hourly_rate")
        transcript = request.data.get("transcript", "")

        if not transcript:
            return Response(
                {"detail": "El transcript es obligatorio"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- llamada a tu IA (ajusta a tu función real) ---
        ai_result = analyze_meeting_transcript(transcript, hourly_rate)

        project = Project.objects.create(
            title=title,
            description=ai_result["description"],
            required_skills=ai_result["required_skills"],
            estimated_hours=ai_result["estimated_hours"],
            hourly_rate=hourly_rate,
            estimated_cost=ai_result["estimated_cost"],
            client_name=client,
        )

        meeting = Meeting.objects.create(
            project=project,
            title=title,
            client_name=client,
            transcript=transcript,
            hourly_rate=hourly_rate,
        )

        meeting_data = self.get_serializer(meeting).data
        meeting_data["project"] = ProjectSerializer(project).data

        return Response(meeting_data, status=status.HTTP_201_CREATED)