from rest_framework import viewsets, permissions,mixins, status
from .models import Project,Meeting
from .serializers import ProjectSerializer,MeetingSerializer
from recruiting.ai_client import analyze_meeting_transcript
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from datetime import timedelta
from django.utils import timezone

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
    permission_classes = [permissions.IsAuthenticated] # Ajusta según necesites

    def create(self, request, *args, **kwargs):
        # 1. Obtener datos
        title = request.data.get("title", "Proyecto desde reunión")
        client = request.data.get("client_name", "")
        hourly_rate = request.data.get("hourly_rate", 0)
        transcript = request.data.get("transcript", "")
        meeting_date = request.data.get("date")

        if not transcript:
            return Response({"detail": "El transcript es obligatorio"}, status=400)

        # 2. Llamar a la IA
        try:
            ai_result = analyze_meeting_transcript(transcript, hourly_rate)
        except Exception as e:
            return Response({"detail": f"Error IA: {str(e)}"}, status=500)

        # 3. Preparar Datos
        summary = ai_result.get("description") or ai_result.get("project_summary", "")
        est_hours = ai_result.get("estimated_hours", 0)
        est_cost = ai_result.get("estimated_cost", 0)
        #req_skills = ["Python", "React", "Test Manual"]
        req_skills = ai_result.get("required_skills", [])
        raw_skills = ai_result.get("required_skills", [])
        
        if isinstance(raw_skills, str):
            req_skills = [s.strip() for s in raw_skills.split(",")]
        # Si ya es una lista, la usamos tal cual
        elif isinstance(raw_skills, list):
            req_skills = raw_skills
        # Si es cualquier otra cosa, ponemos lista vacía para evitar error
        else:
            req_skills = []
        # --- CÁLCULO DE FECHAS ---
        start_date = timezone.now().date()
        
        # Lógica: Si hay horas, dividimos por 40h/semana. Si no, default 4 semanas.
        hours_val = int(est_hours) if est_hours else 160
        weeks = max(1, hours_val / 40)
        end_date = start_date + timedelta(weeks=weeks)
        # -------------------------

        full_description = (
            f"{summary}\n\n"
            f"--- Estimación IA ---\n"
            f"Horas: {est_hours} | Costo: ${est_cost}"
        )

        # 4. Crear Proyecto (CORREGIDO: Sin client_name)
        project = Project.objects.create(
            title=title,
            description=full_description,
            required_skills=req_skills,
            start_date=start_date,
            end_date=end_date,
            # client_name=client  <--- ELIMINADO PORQUE PROVOCABA EL ERROR
        )

        print("--------------------------------------------------")
        print(f"PROYECTO CREADO ID: {project.id}")
        print(f"SKILLS QUE INTENTÉ GUARDAR: {req_skills}")
        
        # Recargamos el objeto desde la base de datos para ver qué se guardó realmente
        project.refresh_from_db()
        print(f"SKILLS EN BASE DE DATOS: {project.required_skills}")
        print("--------------------------------------------------")
        # 5. Crear Reunión
        meeting = Meeting.objects.create(
            project=project,
            title=title,
            client_name=client,       # Aquí SÍ va client_name
            transcript_text=transcript,
            hourly_rate=hourly_rate,
            ai_result=ai_result,
            date=meeting_date,
            created_by=request.user
        )

        meeting_data = self.get_serializer(meeting).data
        meeting_data["project"] = ProjectSerializer(project).data

        return Response(meeting_data, status=status.HTTP_201_CREATED)