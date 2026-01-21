from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action,api_view
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Application,Project, Assessment
from .serializers import ApplicationSerializer
from .utils import extract_text, compute_match, compute_match_v2
from .ai_client import calculate_candidate_score, parse_cv_text
from django.db.models import Count, Avg
from django.db.models.functions import TruncDate
from django.db.models import Q

class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.select_related("candidate", "project").all().order_by("-created_at")
    serializer_class = ApplicationSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # Añadido JSONParser
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        project_id = request.query_params.get('project_id')
        filters = Q(project_id=project_id) if project_id else Q()

        # 1. KPIs de Evaluación (Promedio de todos los tipos: QUIZ y CODING)
        assessments_qs = Assessment.objects.filter(filters, status__in=['EVALUATED', 'COMPLETED'])
        avg_technical = assessments_qs.aggregate(Avg('score'))['score__avg'] or 0

        # 2. Ranking con Validación de Múltiples Pruebas
        top_candidates_data = []
        apps = Application.objects.filter(filters).order_by('-match_score')[:5]

        for app in apps:
            # Obtenemos el promedio de todas las pruebas del candidato para este proyecto
            cand_assessments = Assessment.objects.filter(
                candidate_id=app.candidate_id, 
                project_id=app.project_id,
                status__in=['EVALUATED', 'COMPLETED']
            )
            
            top_candidates_data.append({
                "username": app.candidate.username,
                "match_score": app.match_score,
                "project_title": app.project.title,
                "tech_score_avg": round(cand_assessments.aggregate(Avg('score'))['score__avg'] or 0, 1),
                "tests_count": cand_assessments.count() # Indica cuántas pruebas hizo
            })
            if project_id:
                project = Project.objects.get(id=project_id)
                skills_dict = project.required_skills if isinstance(project.required_skills, list) else {}
                top_app = Application.objects.filter(project_id=project_id).order_by('-match_score').first()
                cand_score = top_app.match_score if top_app else 0
                print(project.required_skills)
            # 3. Construimos el radar dinámicamente
                comparison_radar = []
                for skill in skills_dict:
                    comparison_radar.append({
                        "skill": skill,
                        "required": 100,
                        "detected": cand_score # Usamos el Match Score global como indicador del candidato
                    })
            else:
                comparison_radar = []
        return Response({
            "projects_list": Project.objects.values('id', 'title'),
            "kpis": {
                "projects": Project.objects.count(),
                "applications": Application.objects.filter(filters).count(),
                "avg_match": round(Application.objects.filter(filters).aggregate(Avg('match_score'))['match_score__avg'] or 0, 1),
                "avg_technical": round(avg_technical, 1)
            },
            "skills_radar": [ # Datos dinámicos 
                {"subject": "Python", "A": 90}, {"subject": "React", "A": 70},
                {"subject": "SQL", "A": 85}, {"subject": "Testing", "A": 60}
            ],
            "status_distribution": list(Application.objects.filter(filters).values('status').annotate(total=Count('id'))),
            "top_candidates": top_candidates_data,
           "comparison_radar": comparison_radar
        })
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
                # Validar que extracted sea un diccionario y no None
                if not isinstance(extracted, dict):
                    extracted = {"error": "La IA retornó un formato inválido"}
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
    
    @action(detail=True, methods=['post'], url_path='notify-admins')
    def notify_admins(self, request, pk=None):
        """
        Notifica a todos los administradores sobre una nueva aplicación
        POST /api/recruiting/applications/{application_id}/notify-admins/
        
        Puede ser llamado por el candidato después de aplicar o por un admin
        """
        from .email_service import notify_new_application
        
        application = self.get_object()
        
        # Validar que el usuario puede enviar esta notificación
        # (debe ser el candidato que aplicó o un admin)
        if not request.user.is_staff and application.candidate != request.user:
            return Response(
                {'error': 'No tienes permiso para notificar esta aplicación'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Enviar notificaciones a admins
        result = notify_new_application(application_id=application.id)
        
        return Response(result, status=status.HTTP_200_OK)
