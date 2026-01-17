from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Application
from .serializers import ApplicationSerializer
from .utils import extract_text, compute_match, compute_match_v2
from .ai_client import calculate_candidate_score, parse_cv_text


class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.select_related("candidate", "project").all().order_by("-created_at")
    serializer_class = ApplicationSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # Añadido JSONParser
    permission_classes = [permissions.IsAuthenticated]

    # Si no eres admin (is_staff), solo ves tus propias aplicaciones
    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(candidate=self.request.user)
        return qs

    def perform_create(self, serializer):
        # Procesamiento de CV con IA (código de tu compañero)
        app = serializer.save(candidate=self.request.user)

        # 1. EXTRAER TEXTO DEL ARCHIVO
        if app.cv_file:
            text = extract_text(app.cv_file.path)
            app.parsed_text = text[:20000]

        # 2. ENVIAR A IA PARA JSON
        extracted = {}
        if app.parsed_text:
            try:
                extracted = parse_cv_text(app.parsed_text)
            except Exception as e:
                extracted = {"error": str(e)}

        app.extracted = extracted
        project = serializer.validated_data['project']
        requirements = {
            "title": project.title,
            "skills": project.required_skills,
            "description": project.description
        }

        # 1. Llamamos a la nueva función de calificación
        scores = calculate_candidate_score(extracted, requirements) #
        
        s_score = scores.get("skills_score", 0)
        e_score = scores.get("experience_score", 0)

        # 2. APLICAMOS LOS PESOS (Skills 40%, Experience 60%)
        # Fórmula: (Skills * 0.4) + (Experience * 0.6)
        final_score = (s_score * 0.4) + (e_score * 0.6) #

        print(f"📊 Calificación: Skills({s_score}) + Exp({e_score}) = Total: {final_score}")

        # 3. Guardamos la postulación con la nueva nota
        serializer.save(
            extracted=extracted,
            score=final_score,
            ai_analysis=scores.get("justification", "Sin análisis disponible"),
            hard_skills=extracted.get("skills", {}).get("hard", []),
            soft_skills=extracted.get("skills", {}).get("soft", [])
        )

        app.match_score = final_score*10
        app.save()

    # Endpoint personalizado para actualizar el estado (solo admin)
    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAdminUser])
    def update_status(self, request, pk=None):
        """
        Endpoint para que los admins actualicen el estado de una aplicación.
        PATCH /api/recruiting/applications/{id}/update_status/
        Body: {"status": "REVIEW"}
        """
        application = self.get_object()
        new_status = request.data.get('status')
        
        # Validar que el estado sea válido
        valid_statuses = [choice[0] for choice in Application.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {'error': f'Estado inválido. Opciones: {valid_statuses}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        application.status = new_status
        application.save()
        
        serializer = self.get_serializer(application)
        return Response(serializer.data)

    # Permitir que admins actualicen el estado mediante PATCH normal
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Si el usuario es admin, permitir actualizar el status
        if request.user.is_staff and 'status' in request.data:
            # Validar que el estado sea válido
            new_status = request.data.get('status')
            valid_statuses = [choice[0] for choice in Application.STATUS_CHOICES]
            
            if new_status not in valid_statuses:
                return Response(
                    {'error': f'Estado inválido. Opciones: {valid_statuses}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            instance.status = new_status
            instance.save()
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
