import json
from rest_framework import viewsets, permissions, mixins, status
from .models import Project, Meeting
from .serializers import ProjectSerializer, MeetingSerializer
from recruiting.ai_client import analyze_meeting_transcript
from rest_framework.response import Response
from datetime import timedelta
from django.utils import timezone
import base64
import tempfile
import os
from openai import OpenAI
from django.conf import settings
from django.contrib.auth.models import User

# Inicialización global del cliente OpenAI
client = OpenAI(api_key=settings.OPENAI_API_KEY)

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
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        data = request.data
        
        # 1. Obtención de metadatos básicos
        title = data.get("title", "Proyecto desde reunión")
        client_name_str = data.get("client_name", "Desconocido")
        hourly_rate = data.get("hourly_rate", 50)
        meeting_date = data.get("date", timezone.now())
        transcript_input = data.get("transcript", "")

        # 2. Procesamiento de la fuente de transcripción (Texto o Audio Binario)
        transcript_text = ""
        
        if isinstance(transcript_input, dict) and "$content" in transcript_input:
            print("📦 Procesando archivo binario desde Power Automate...")
            try:
                file_data = base64.b64decode(transcript_input["$content"])
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
                    temp_video.write(file_data)
                    temp_path = temp_video.name

                with open(temp_path, "rb") as audio_file:
                    transcript_res = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="es"
                    )
                transcript_text = transcript_res.text
                print(f"📝 Transcripción Whisper completada: {transcript_text[:50]}...")
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as e:
                return Response({"detail": f"Error procesando audio: {str(e)}"}, status=400)
        else:
            # Es texto plano (enviado desde el Frontend)
            transcript_text = transcript_input

        if not transcript_text:
            return Response({"detail": "No se recibió texto ni audio válido"}, status=400)

        # 3. Llamada ÚNICA a la IA para análisis
        try:
            ai_result = analyze_meeting_transcript(transcript_text, hourly_rate)
        except Exception as e:
            return Response({"detail": f"Error IA: {str(e)}"}, status=500)

        # 4. Preparación de datos del proyecto
        summary = ai_result.get("project_summary") or ai_result.get("description", "")
        est_hours = ai_result.get("estimated_hours", 0)
        est_cost = ai_result.get("estimated_cost", 0)
        project_title = ai_result.get("project_title", "Proyecto por defecto")
        
        print("\n" + "="*50)
        print("🤖 RESULTADO COMPLETO DE LA IA:")
        print(json.dumps(ai_result, indent=4, ensure_ascii=False))
        print("="*50 + "\n")
        # Limpieza de skills
        raw_skills = ai_result.get("required_skills", [])
        if isinstance(raw_skills, str):
            req_skills = [s.strip() for s in raw_skills.split(",")]
        elif isinstance(raw_skills, list):
            req_skills = raw_skills
        else:
            req_skills = []

        # Cálculo de fechas
        start_date = timezone.now().date()
        hours_val = int(est_hours) if est_hours else 160
        weeks = max(1, hours_val / 40)
        end_date = start_date + timedelta(weeks=weeks)

        full_description = (
            f"{summary}\n\n"
            f"--- Estimación IA ---\n"
            f"Horas: {est_hours} | Costo: ${est_cost}"
        )

        # 5. Guardar Proyecto en Base de Datos
        try:
            project = Project.objects.create(
                title=project_title,
                description=full_description,
                required_skills=req_skills,
                start_date=start_date,
                end_date=end_date
            )

            # 6. Manejo de Usuario (Power Automate no tiene sesión)
            current_user = request.user
            if not current_user or current_user.is_anonymous:
                current_user = User.objects.filter(is_superuser=True).first()

            # 7. Crear la Reunión asociada
            meeting = Meeting.objects.create(
                project=project,
                title=title,
                client_name=client_name_str,
                transcript_text=transcript_text,
                hourly_rate=hourly_rate,
                ai_result=ai_result,
                date=meeting_date,
                created_by=current_user
            )

            # 8. Respuesta final
            meeting_data = self.get_serializer(meeting).data
            meeting_data["project"] = ProjectSerializer(project).data
            return Response(meeting_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"detail": f"Error al guardar en BD: {str(e)}"}, status=500)