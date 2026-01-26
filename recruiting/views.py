from warnings import filters
from httpx import request
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
        status_filter = request.query_params.get('status') # Recibimos el filtro del gráfico circular
        filters = Q()
        # Empezamos con una consulta vacía (trae todo por defecto)
        ranking_data = []

        # Si hay proyecto, filtramos por proyecto
        if project_id and project_id != 'null' and project_id != '':
            filters &= Q(project_id=project_id)

        # Si hay estado (del gráfico circular), filtramos por estado
        if status_filter and status_filter != 'null' and status_filter != '':
            filters &= Q(status=status_filter)

        if project_id: filters &= Q(project_id=project_id)
        if status_filter: filters &= Q(status=status_filter)
        quiz_weight_raw = float(request.query_params.get('quiz_weight', 50))
        quiz_w = quiz_weight_raw / 100
        coding_w = 1 - quiz_w
        applications = Application.objects.filter(filters).select_related('candidate', 'project')
  

        for app in applications:
            # 3. Obtenemos los promedios de ese candidato por tipo en MySQL
            # Solo tomamos evaluaciones finalizadas (EVALUATED o COMPLETED)
            base_scores = Assessment.objects.filter(
                candidate_id=app.candidate_id,
                project_id=app.project_id,
                status__in=['EVALUATED']
            ).values('assessment_type').annotate(average=Avg('score'))

            # Inicializamos variables para el cálculo
            avg_quiz = 0
            avg_coding = 0
            
            for score_data in base_scores:
                if score_data['assessment_type'] == 'QUIZ':
                    avg_quiz = score_data['average']
                elif score_data['assessment_type'] == 'CODING':
                    avg_coding = score_data['average']


            weighted_technical_avg = (avg_quiz * quiz_w) + (avg_coding * coding_w)

            ranking_data.append({
                "candidate_name": app.candidate.email, # Usamos el email como en tu dashboard
                "project_title": app.project.title,
                "num_pruebas_pendiente": Assessment.objects.filter(candidate_id=app.candidate_id, project_id=app.project_id, status='PENDING').count(),
                "ia_match": f"{app.match_score}%", # El score de 60/40 de tu US03
                "promedio_tecnico": round(weighted_technical_avg, 1), # Este es el que cambia con el slider
                "num_pruebas": Assessment.objects.filter(candidate_id=app.candidate_id, project_id=app.project_id, status='EVALUATED').count(),
                "status": app.status
            })

        # 5. Reordenamos el ranking basado en el nuevo promedio técnico calculado
        # Esto permite que el ranking cambie en tiempo real en el frontend
        ranking_data = sorted(ranking_data, key=lambda x: (x['promedio_tecnico'], x['ia_match']), reverse=True)

        # 1. KPIs de Evaluación (Promedio de todos los tipos: QUIZ y CODING)
        assessments_qs = Assessment.objects.filter(filters, status__in=['EVALUATED'])
        avg_technical = assessments_qs.aggregate(Avg('score'))['score__avg'] or 0
        # Obtenemos los conteos para el gráfico de pastel
        status_counts = Application.objects.filter(filters).values('status').annotate(total=Count('id'))
    
        # Mapeo de nombres técnicos a etiquetas amigables para el Dashboard
        friendly_status_map = {
            'APPROVED': 'Aprobados',
            'REVIEW': 'En Revisión',
            'SUBMITTED': 'Esperando Revisión',
            'REJECTED': 'Rechazados'
        }
        pie_data = [
        {
            "name": friendly_status_map.get(s['status'], s['status']),
            "value": s['total']
        } for s in status_counts
        ]

        # Calculamos el promedio de aciertos por tipo de prueba
        type_performance = (
            Assessment.objects.filter(filters, status__in=['EVALUATED', 'COMPLETED'])
            .values('assessment_type')
            .annotate(avg_score=Avg('score'))
            .order_by('-avg_score')
        )

        # Mapeo de etiquetas para el frontend
        type_data = [
            {
                "type": "Prueba de Código" if item['assessment_type'] == 'CODING' else "Cuestionario (Quiz)",
                "percentage": round(item['avg_score'], 1)
            } for item in type_performance
        ]

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
          
        return Response({
            "projects_list": Project.objects.values('id', 'title'),
            "kpis": {
                "projects": Project.objects.count(),
                "applications": Application.objects.filter(filters).count(),
                "avg_match": round(Application.objects.filter(filters).aggregate(Avg('match_score'))['match_score__avg'] or 0, 1),
                "avg_technical": round(avg_technical, 1)
            },
            "status_distribution": list(Application.objects.filter(filters).values('status').annotate(total=Count('id'))),
            "top_candidates": top_candidates_data,
            "pie_data": pie_data, # Nuevos datos para el gráfico de pastel
            "type_performance": type_data, # Nueva data para las barras
            "ranking_candidates": ranking_data,
            "current_weights": {
            "quiz": quiz_weight_raw,
            "coding": 100 - quiz_weight_raw
        }
        })
    # Si no eres admin (is_staff), solo ves tus propias aplicaciones
    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(candidate=self.request.user)
        return qs

    def perform_create(self, serializer):
        """Procesamiento de CV con IA"""
        import traceback
        
        try:
            app = serializer.save(candidate=self.request.user)
            print(f"✅ Application guardada: {app.id}")

            # 1. EXTRAER TEXTO DEL ARCHIVO
            if app.cv_file:
                try:
                    print(f"📄 Extrayendo texto del CV: {app.cv_file.name}")
                    # Pasar el FileField directamente (funciona con Cloudinary y local)
                    text = extract_text(app.cv_file)
                    app.parsed_text = text[:20000]
                    print(f"✅ Texto extraído: {len(text)} caracteres")
                except Exception as e:
                    print(f"❌ Error extrayendo texto: {str(e)}")
                    traceback.print_exc()
                    app.parsed_text = ""

            # 2. ENVIAR A IA PARA JSON
            extracted = {}
            if app.parsed_text:
                try:
                    print(f"🤖 Enviando a IA para parsear CV...")
                    extracted = parse_cv_text(app.parsed_text)
                    # Validar que extracted sea un diccionario y no None
                    if not isinstance(extracted, dict):
                        extracted = {"error": "La IA retornó un formato inválido"}
                    print(f"✅ CV parseado por IA")
                except Exception as e:
                    print(f"❌ Error en parse_cv_text: {str(e)}")
                    traceback.print_exc()
                    extracted = {"error": str(e)}

            app.extracted = extracted
            project = serializer.validated_data['project']
            requirements = {
                "title": project.title,
                "skills": project.required_skills,
                "description": project.description
            }

            # 3. Llamamos a la función de calificación
            try:
                print(f"📊 Calculando score del candidato...")
                scores = calculate_candidate_score(extracted, requirements)
                
                s_score = scores.get("skills_score", 0)
                e_score = scores.get("experience_score", 0)

                # APLICAMOS LOS PESOS (Skills 40%, Experience 60%)
                final_score = (s_score * 0.4) + (e_score * 0.6)
                print(f"📊 Calificación: Skills({s_score}) + Exp({e_score}) = Total: {final_score}")
            except Exception as e:
                print(f"❌ Error calculando score: {str(e)}")
                traceback.print_exc()
                scores = {"skills_score": 0, "experience_score": 0, "justification": "Error en cálculo"}
                final_score = 0

            # 4. Guardamos la postulación
            try:
                app.match_score = final_score * 10
                app.ai_analysis = scores.get("justification", "Sin análisis disponible")
                app.save()
                print(f"✅ Application actualizada con score: {app.match_score}")
            except Exception as e:
                print(f"❌ Error guardando application: {str(e)}")
                traceback.print_exc()
                raise
            
            # 5. Enviar notificaciones por email a admins
            try:
                from .email_service import notify_new_application
                notify_new_application(app.id)
                print(f"✅ Notificaciones enviadas a admins para application {app.id}")
            except Exception as e:
                print(f"⚠️ Error enviando notificaciones (no crítico): {str(e)}")
                # No fallar si falla el email
                
        except Exception as e:
            print(f"❌❌❌ ERROR CRÍTICO en perform_create: {str(e)}")
            traceback.print_exc()
            raise

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
