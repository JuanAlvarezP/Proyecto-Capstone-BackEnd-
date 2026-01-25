from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.conf import settings
import json
import logging
import re
from .models import Assessment, Question, CandidateAnswer
from .serializers import (
    AssessmentListSerializer, AssessmentDetailSerializer, AssessmentCreateSerializer,
    QuestionSerializer, QuestionCreateSerializer, CandidateAnswerSerializer,
    ApplicationAnalysisInputSerializer, ApplicationAnalysisOutputSerializer
)
from .openai_service import OpenAIAssessmentService

logger = logging.getLogger(__name__)


class AssessmentViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar pruebas técnicas"""
    queryset = Assessment.objects.select_related("candidate", "project").prefetch_related("questions").all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return AssessmentListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return AssessmentCreateSerializer
        return AssessmentDetailSerializer
    
    def get_queryset(self):
        """Filtrar según tipo de usuario"""
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            # Candidatos solo ven sus propias pruebas
            qs = qs.filter(candidate=self.request.user)
        return qs
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def generate_questions(self, request, pk=None):
        """
        Endpoint para generar preguntas con OpenAI
        POST /api/assessments/{id}/generate_questions/
        Body: {
            "topic": "Python avanzado",
            "num_questions": 10,  # Para QUIZ
            "num_challenges": 1,  # Para CODING (siempre 1 desafío)
            "language": "es",  # o "en"
            "include_code_snippets": true  # Generar fragmentos de código en preguntas QUIZ
        }
        """
        assessment = self.get_object()
        topic = request.data.get('topic')
        num_questions = request.data.get('num_questions', 10)
        num_challenges = request.data.get('num_challenges', 1)
        language = request.data.get('language', 'es')
        include_code_snippets = request.data.get('include_code_snippets', False)
        
        if not topic:
            return Response(
                {'error': 'El campo "topic" es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            ai_service = OpenAIAssessmentService()
            generated_questions = []
            
            if assessment.assessment_type == 'QUIZ':
                # Generar preguntas de cuestionario
                questions_data = ai_service.generate_quiz_questions(
                    topic=topic,
                    difficulty=assessment.difficulty,
                    num_questions=num_questions,
                    language=language,
                    include_code_snippets=include_code_snippets
                )
                
                for idx, q_data in enumerate(questions_data):
                    correct_answer_value = str(q_data.get('correct_answer', ''))
                    question_text = q_data['question_text']
                    code_snippet = q_data.get('code_snippet', '')
                    
                    # Si no hay code_snippet pero el texto menciona código, extraerlo
                    if not code_snippet:
                        code_snippet = self._extract_code_from_text(question_text)
                    
                    # Validar que si se menciona código, exista code_snippet
                    if self._mentions_code(question_text) and not code_snippet:
                        logger.warning(
                            f"Pregunta {idx+1} menciona código pero no tiene code_snippet: {question_text[:100]}"
                        )
                    
                    question = Question.objects.create(
                        assessment=assessment,
                        question_type=q_data.get('question_type', 'MULTIPLE_CHOICE'),
                        question_text=question_text,
                        code_snippet=code_snippet,
                        options=q_data.get('options', []),
                        correct_answer=correct_answer_value,
                        explanation=q_data.get('explanation', ''),
                        points=q_data.get('points', 10),
                        order=idx,
                        generated_by_ai=True,
                        ai_prompt=f"Topic: {topic}, Difficulty: {assessment.difficulty}, Include Code: {include_code_snippets}"
                    )
                    print(f"✅ Pregunta {idx+1} guardada:")
                    print(f"   ID: {question.id}")
                    print(f"   Texto: {question.question_text[:60]}...")
                    print(f"   Opciones: {question.options}")
                    print(f"   code_snippet: {len(code_snippet)} caracteres")
                    print(f"   correct_answer: '{question.correct_answer}' (tipo: {type(question.correct_answer).__name__})")
                    generated_questions.append(question)
                    
            elif assessment.assessment_type == 'CODING':
                # Generar desafíos de código
                prog_lang = request.data.get('programming_language', 'python')
                challenges_data = ai_service.generate_coding_challenges(
                    topic=topic,
                    difficulty=assessment.difficulty,
                    num_challenges=num_challenges,
                    language=prog_lang
                )
                
                for idx, c_data in enumerate(challenges_data):
                    question = Question.objects.create(
                        assessment=assessment,
                        question_type='CODE',
                        question_text=c_data['question_text'],
                        code_snippet=c_data.get('code_snippet', ''),
                        programming_language=c_data.get('programming_language', prog_lang),
                        test_cases=c_data.get('test_cases', []),
                        correct_answer='',  # No hay respuesta única en código
                        explanation=c_data.get('explanation', ''),
                        points=c_data.get('points', 20),
                        order=idx,
                        generated_by_ai=True,
                        ai_prompt=f"Topic: {topic}, Difficulty: {assessment.difficulty}, Language: {prog_lang}"
                    )
                    generated_questions.append(question)
            
            serializer = QuestionSerializer(generated_questions, many=True, context={'request': request})
            return Response({
                'message': f'{len(generated_questions)} preguntas generadas exitosamente',
                'questions': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Error al generar preguntas: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """
        Iniciar una prueba (cambiar estado a IN_PROGRESS)
        POST /api/assessments/{id}/start/
        """
        assessment = self.get_object()
        
        if assessment.status != 'PENDING':
            return Response(
                {'error': 'Esta prueba ya fue iniciada o completada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        assessment.status = 'IN_PROGRESS'
        assessment.started_at = timezone.now()
        assessment.save()
        
        serializer = self.get_serializer(assessment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Enviar/completar una prueba
        POST /api/assessments/{id}/submit/
        """
        assessment = self.get_object()
        
        if assessment.status == 'COMPLETED':
            return Response(
                {'error': 'Esta prueba ya fue enviada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        assessment.status = 'COMPLETED'
        assessment.completed_at = timezone.now()
        
        # Calcular puntuación total
        total_points = sum(q.points for q in assessment.questions.all())
        earned_points = sum(
            CandidateAnswer.objects.filter(
                question__assessment=assessment,
                candidate=request.user
            ).values_list('points_earned', flat=True)
        )
        
        if total_points > 0:
            assessment.score = (earned_points / total_points) * 100
        else:
            assessment.score = 0
            
        assessment.save()
        
        # Enviar notificaciones por email
        from .email_service import notify_assessment_completed
        try:
            notify_assessment_completed(assessment.id)
            logger.info(f"✅ Notificaciones enviadas para assessment {assessment.id}")
        except Exception as e:
            logger.error(f"❌ Error enviando notificaciones para assessment {assessment.id}: {str(e)}")
        
        serializer = self.get_serializer(assessment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def evaluate_quiz(self, request, pk=None):
        """
        Evalúa automáticamente un cuestionario comparando las respuestas 
        del candidato con las respuestas correctas
        POST /api/assessments/{id}/evaluate_quiz/
        """
        assessment = self.get_object()
        
        # Verificar que sea tipo QUIZ
        if assessment.assessment_type != 'QUIZ':
            return Response(
                {'error': 'Este endpoint solo funciona con evaluaciones tipo QUIZ'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener todas las preguntas del assessment
        questions = assessment.questions.all()
        
        # Obtener todas las respuestas del candidato para este assessment
        answers = CandidateAnswer.objects.filter(
            question__assessment=assessment,
            candidate=request.user
        )
        
        total_points = 0
        max_possible_points = 0
        evaluated_count = 0
        results_detail = []
        
        for question in questions:
            max_possible_points += question.points
            
            try:
                answer = answers.get(question=question)
                
                # Determinar si la respuesta es correcta según el tipo de pregunta
                is_correct = False
                
                if question.question_type == 'MULTIPLE_CHOICE':
                    # Para opción múltiple, comparar el índice seleccionado
                    # El frontend puede enviar answer_text (string "0", "1", etc.) o selected_option_index (int)
                    correct_answer_str = str(question.correct_answer).strip()
                    user_answer_str = str(answer.answer_text).strip() if answer.answer_text else str(answer.selected_option_index)
                    
                    is_correct = user_answer_str == correct_answer_str
                    
                    print(f"\n🔍 Evaluando pregunta {question.id}:")
                    print(f"   Pregunta: {question.question_text[:60]}...")
                    print(f"   Opciones: {question.options}")
                    print(f"   Respuesta correcta (backend): '{correct_answer_str}'")
                    print(f"   Respuesta usuario (answer_text): '{answer.answer_text}'")
                    print(f"   Respuesta usuario (selected_option_index): {answer.selected_option_index}")
                    print(f"   ¿Es correcta?: {is_correct}")
                
                elif question.question_type == 'TRUE_FALSE':
                    # Para verdadero/falso, comparar directamente
                    is_correct = answer.answer_text.lower() == question.correct_answer.lower()
                
                elif question.question_type == 'SHORT_ANSWER':
                    # Para respuesta corta, comparar texto (case-insensitive)
                    is_correct = answer.answer_text.lower().strip() == question.correct_answer.lower().strip()
                
                # Actualizar la respuesta
                answer.is_correct = is_correct
                answer.points_earned = question.points if is_correct else 0
                answer.feedback = question.explanation if question.explanation else ''
                answer.save()
                
                if is_correct:
                    total_points += question.points
                
                evaluated_count += 1
                
                results_detail.append({
                    'question_id': question.id,
                    'question_text': question.question_text[:50] + '...',
                    'is_correct': is_correct,
                    'points_earned': answer.points_earned,
                    'max_points': question.points
                })
                
            except CandidateAnswer.DoesNotExist:
                # Pregunta sin respuesta
                results_detail.append({
                    'question_id': question.id,
                    'question_text': question.question_text[:50] + '...',
                    'is_correct': False,
                    'points_earned': 0,
                    'max_points': question.points,
                    'error': 'Sin respuesta'
                })
                continue
        
        # Calcular porcentaje
        score_percentage = (total_points / max_possible_points * 100) if max_possible_points > 0 else 0
        
        # Actualizar el assessment
        assessment.score = score_percentage
        assessment.status = 'EVALUATED'
        assessment.save()
        
        return Response({
            'assessment_id': assessment.id,
            'total_points': total_points,
            'max_possible_points': max_possible_points,
            'score_percentage': round(score_percentage, 2),
            'evaluated_answers': evaluated_count,
            'total_questions': questions.count(),
            'passed': score_percentage >= assessment.passing_score,
            'results_detail': results_detail
        })
    
    def _analyze_application_logic(self, application_id):
        """Lógica compartida para analizar aplicación"""
        try:
            # Usar el servicio OpenAI para analizar
            ai_service = OpenAIAssessmentService()
            analysis_result = ai_service.analyze_application_for_assessment(application_id)
            
            # Reestructurar para match con formato requerido
            response_data = {
                "suggested_title": analysis_result.get('suggested_title'),
                "suggested_description": analysis_result.get('suggested_description'),
                "suggested_type": analysis_result.get('suggested_type'),
                "suggested_difficulty": analysis_result.get('suggested_difficulty'),
                "suggested_time_minutes": analysis_result.get('suggested_time_minutes'),
                "suggested_passing_score": analysis_result.get('suggested_passing_score'),
                "suggested_num_questions": analysis_result.get('suggested_num_questions'),
                "suggested_programming_language": analysis_result.get('suggested_programming_language'),
                "analysis_reasoning": {
                    "difficulty_reason": analysis_result.get('difficulty_reason', ''),
                    "time_reason": analysis_result.get('time_reason', ''),
                    "score_reason": analysis_result.get('score_reason', ''),
                    "type_reason": analysis_result.get('type_reason', '')
                },
                "detected_skills": analysis_result.get('detected_skills', []),
                "candidate_experience_level": analysis_result.get('candidate_experience_level'),
                "project_complexity": analysis_result.get('project_complexity'),
                "analyzed_at": analysis_result.get('analyzed_at')
            }
            
            # Agregar flag de fallback si existe
            if analysis_result.get('fallback_used'):
                response_data['fallback_used'] = True
            
            # Validar output
            output_serializer = ApplicationAnalysisOutputSerializer(data=analysis_result)
            if not output_serializer.is_valid():
                logger.warning(f"Output validation failed: {output_serializer.errors}")
            
            logger.info(f"✅ Análisis completado para application_id={application_id}")
            return Response(response_data, status=status.HTTP_200_OK)
            
        except ValueError as e:
            # Application no encontrada
            logger.error(f"Application not found: {str(e)}")
            return Response(
                {'error': 'Application not found', 'detail': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            # Error general
            logger.error(f"Error analyzing application: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Error analyzing application', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser], url_path='analyze-application')
    def analyze_application_body(self, request):
        """
        Analiza una aplicación con ID en el body
        POST /api/assessments/analyze-application/
        Body: { "application_id": 123 }
        """
        input_serializer = ApplicationAnalysisInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'details': input_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        application_id = input_serializer.validated_data['application_id']
        return self._analyze_application_logic(application_id)
    
    def analyze_application_url(self, request, app_id=None):
        """
        Analiza una aplicación con ID en la URL (ruta manual en urls.py)
        POST /api/assessments/analyze-application/{id}/
        """
        try:
            application_id = int(app_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'application_id debe ser un número entero'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return self._analyze_application_logic(application_id)
    
    @action(detail=True, methods=['post'], url_path='send-invitation', permission_classes=[permissions.IsAdminUser])
    def send_invitation(self, request, pk=None):
        """
        Envía invitaciones por email a múltiples usuarios para realizar una evaluación
        POST /api/assessments/assessments/{assessment_id}/send-invitation/
        
        Body:
        {
            "user_ids": [1, 2, 3],
            "custom_message": "Mensaje opcional personalizado"
        }
        """
        from .email_service import send_assessment_invitation
        
        assessment = self.get_object()
        user_ids = request.data.get('user_ids', [])
        custom_message = request.data.get('custom_message')
        
        # Validar que se proporcionaron user_ids
        if not user_ids or not isinstance(user_ids, list):
            return Response(
                {'error': 'user_ids debe ser una lista de IDs de usuarios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que los usuarios existen
        from django.contrib.auth.models import User
        existing_users = User.objects.filter(id__in=user_ids).values_list('id', flat=True)
        invalid_ids = set(user_ids) - set(existing_users)
        
        if invalid_ids:
            return Response(
                {
                    'error': f'Los siguientes user_ids no existen: {list(invalid_ids)}',
                    'valid_ids': list(existing_users)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Enviar invitaciones
        result = send_assessment_invitation(
            assessment_id=assessment.id,
            user_ids=list(existing_users),
            custom_message=custom_message
        )
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='notify-completed', permission_classes=[permissions.IsAuthenticated])
    def notify_completed(self, request, pk=None):
        """
        Notifica que una evaluación ha sido completada
        - Al candidato: confirmación de recepción
        - A los admins: nueva evaluación para revisar
        
        POST /api/assessments/assessments/{assessment_id}/notify-completed/
        """
        from .email_service import notify_assessment_completed
        
        assessment = self.get_object()
        
        # Validar que el usuario puede notificar esta evaluación
        # (debe ser el candidato o un admin)
        if not request.user.is_staff and assessment.candidate != request.user:
            return Response(
                {'error': 'No tienes permiso para notificar esta evaluación'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validar que la evaluación está completada
        if assessment.status != 'COMPLETED':
            return Response(
                {
                    'error': f'La evaluación debe estar en estado COMPLETED. Estado actual: {assessment.status}',
                    'current_status': assessment.status
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Enviar notificaciones
        result = notify_assessment_completed(assessment_id=assessment.id)
        
        return Response(result, status=status.HTTP_200_OK)
    
    def _extract_code_from_text(self, text):
        """
        Extrae bloques de código del texto usando regex.
        Detecta bloques con triple backticks (```código```) o indentación especial.
        
        Returns:
            str: El código extraído o cadena vacía
        """
        # Patrón 1: Triple backticks con o sin lenguaje (```python ... ``` o ``` ... ```)
        pattern1 = r'```(?:\w+)?\s*\n(.*?)\n```'
        match = re.search(pattern1, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Patrón 2: Backticks simples multilínea (`código`)
        pattern2 = r'`([^`]+)`'
        matches = re.findall(pattern2, text)
        # Si hay matches largos (probablemente código), retornar el más largo
        if matches:
            longest = max(matches, key=len)
            if len(longest) > 20:  # Evitar extraer palabras simples
                return longest.strip()
        
        return ''
    
    def _mentions_code(self, text):
        """
        Detecta si el texto de la pregunta menciona código.
        
        Returns:
            bool: True si menciona código
        """
        # Frases completas que claramente mencionan código
        explicit_phrases = [
            'siguiente código', 'siguiente codigo',
            'código anterior', 'codigo anterior',
            'salida del', 'resultado del código', 'resultado del codigo',
            'qué imprime', 'que imprime',
            'qué devuelve', 'que devuelve',
            'ejecutar el', 'execute the',
            'output of',
            'following code',
            'above code',
            'código proporcionado', 'codigo proporcionado',
            'provided code',
            'código mostrado', 'codigo mostrado'
        ]
        
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in explicit_phrases)


class QuestionViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar preguntas"""
    queryset = Question.objects.select_related("assessment").all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.user.is_staff:
            return QuestionCreateSerializer
        return QuestionSerializer
    
    def get_queryset(self):
        """Filtrar según tipo de usuario"""
        qs = super().get_queryset()
        assessment_id = self.request.query_params.get('assessment')
        
        if assessment_id:
            qs = qs.filter(assessment_id=assessment_id)
            
        if not self.request.user.is_staff:
            # Candidatos solo ven preguntas de sus pruebas
            qs = qs.filter(assessment__candidate=self.request.user)
            
        return qs


class CandidateAnswerViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar respuestas de candidatos"""
    queryset = CandidateAnswer.objects.select_related("question", "candidate").all()
    serializer_class = CandidateAnswerSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filtrar según tipo de usuario y query params"""
        qs = super().get_queryset()
        
        # Obtener parámetros de filtrado
        assessment_id = self.request.query_params.get('assessment')
        question_id = self.request.query_params.get('question')
        
        print(f"\n🔍 FILTRADO DE RESPUESTAS:")
        print(f"   Assessment ID solicitado: {assessment_id}")
        print(f"   Question ID solicitado: {question_id}")
        print(f"   Usuario: {self.request.user.username}")
        
        # DEBUG: Mostrar estado antes de filtrar
        if assessment_id:
            # Verificar cuántas respuestas existen en total para este usuario
            total_answers = CandidateAnswer.objects.filter(candidate=self.request.user).count() if not self.request.user.is_staff else CandidateAnswer.objects.all().count()
            print(f"   📊 Total respuestas en DB: {total_answers}")
            
            # Verificar cuántas preguntas tiene este assessment
            from .models import Assessment
            try:
                assessment = Assessment.objects.get(id=assessment_id)
                questions_count = assessment.questions.count()
                print(f"   📋 Preguntas en assessment {assessment_id}: {questions_count}")
                
                # Ver si hay respuestas para esas preguntas
                question_ids = list(assessment.questions.values_list('id', flat=True))
                print(f"   🔑 IDs de preguntas: {question_ids}")
                
                answers_for_questions = CandidateAnswer.objects.filter(question_id__in=question_ids)
                if self.request.user.is_staff:
                    answers_count = answers_for_questions.count()
                    print(f"   💬 Respuestas existentes para esas preguntas (todos los usuarios): {answers_count}")
                else:
                    answers_count = answers_for_questions.filter(candidate=self.request.user).count()
                    print(f"   💬 Respuestas existentes para esas preguntas (tu usuario): {answers_count}")
                    
            except Assessment.DoesNotExist:
                print(f"   ❌ Assessment {assessment_id} no existe")
        
        # Filtrar por assessment (a través de question__assessment)
        if assessment_id:
            qs = qs.filter(question__assessment_id=assessment_id)
            print(f"   ✅ Filtrando por question__assessment_id={assessment_id}")
        
        # Filtrar por question
        if question_id:
            qs = qs.filter(question_id=question_id)
            print(f"   ✅ Filtrando por question_id={question_id}")
        
        if not self.request.user.is_staff:
            # Candidatos solo ven sus propias respuestas
            qs = qs.filter(candidate=self.request.user)
            print(f"   ✅ Filtrando por candidate={self.request.user.id}")
        
        # Log de resultados
        results = list(qs.values_list('id', 'question__assessment_id', 'question_id', 'candidate__username'))
        print(f"   📊 Respuestas encontradas: {len(results)}")
        for answer_id, assessment, question, username in results[:5]:  # Mostrar máximo 5
            print(f"      - Answer ID={answer_id}, Assessment={assessment}, Question={question}, Usuario={username}")
        if len(results) > 5:
            print(f"      ... y {len(results) - 5} más")
        print()
            
        return qs
    
    def perform_create(self, serializer):
        """Guardar respuesta y evaluar automáticamente"""
        answer = serializer.save(candidate=self.request.user)
        
        # Auto-evaluación para preguntas de opción múltiple
        if answer.question.question_type == 'MULTIPLE_CHOICE':
            correct_idx = int(answer.question.correct_answer)
            if answer.selected_option_index == correct_idx:
                answer.is_correct = True
                answer.points_earned = answer.question.points
            else:
                answer.is_correct = False
                answer.points_earned = 0
            answer.save()
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def evaluate_code(self, request, pk=None):
        """
        Evaluar código usando OpenAI
        POST /api/answers/{id}/evaluate_code/
        """
        answer = self.get_object()
        
        if answer.question.question_type != 'CODE':
            return Response(
                {'error': 'Esta pregunta no es de tipo código'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            ai_service = OpenAIAssessmentService()
            
            # Obtener el nivel de dificultad del assessment
            assessment = answer.question.assessment
            difficulty = assessment.difficulty if assessment else 'MEDIUM'
            
            evaluation = ai_service.evaluate_code_answer(
                question_text=answer.question.question_text,
                candidate_code=answer.code_answer or answer.answer_text,
                test_cases=answer.question.test_cases,
                language=answer.question.programming_language,
                difficulty=difficulty  # Pasar la dificultad
            )
            
            # Obtener el score
            score_percentage = evaluation.get('score_percentage', 0)
            is_correct = evaluation.get('is_correct', False)
            
            # 🔥 SISTEMA DE VALIDACIÓN ULTRA-ROBUSTO CON 5 CAPAS 🔥
            test_results = evaluation.get('test_results', [])
            min_scores = {'EASY': 80, 'MEDIUM': 75, 'HARD': 70}
            min_score = min_scores.get(difficulty, 75)
            
            # Calcular cuántos tests pasaron
            passed_count = sum(1 for t in test_results if t.get('passed', False))
            total_count = len(test_results) if test_results else 0
            all_tests_passed = (total_count > 0 and passed_count == total_count)
            pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0
            
            print(f"\n🔍 DEBUG VALIDACIÓN VIEWS:")
            print(f"   Score original de OpenAI: {score_percentage}%")
            print(f"   is_correct: {is_correct}")
            print(f"   Tests pasados: {passed_count}/{total_count} ({pass_rate:.0f}%)")
            print(f"   Score mínimo para {difficulty}: {min_score}%")
            
            # 🔴 CAPA 1: Si is_correct es True, FORZAR puntaje mínimo
            if is_correct:
                if score_percentage < min_score:
                    print(f"   ⚠️ CAPA 1: is_correct=True pero score={score_percentage}% < {min_score}%")
                    print(f"   ✅ CORRECCIÓN: Forzando score a {min_score}%")
                    score_percentage = min_score
                    evaluation['score_percentage'] = min_score
            
            # 🔴 CAPA 2: Si TODOS los tests pasaron, FORZAR puntaje mínimo
            if all_tests_passed:
                if score_percentage < min_score:
                    print(f"   ⚠️ CAPA 2: Todos los tests pasaron pero score={score_percentage}% < {min_score}%")
                    print(f"   ✅ CORRECCIÓN: Forzando score a {min_score}%")
                    score_percentage = min_score
                    evaluation['score_percentage'] = min_score
                is_correct = True
                evaluation['is_correct'] = True
            
            # 🔴 CAPA 3: Si 80%+ de tests pasaron, dar al menos 70%
            if pass_rate >= 80 and score_percentage < 70:
                print(f"   ⚠️ CAPA 3: {pass_rate:.0f}% tests pasaron pero score={score_percentage}%")
                print(f"   ✅ CORRECCIÓN: Forzando score mínimo a 70%")
                score_percentage = max(70, score_percentage)
                evaluation['score_percentage'] = score_percentage
            
            # 🔴 CAPA 4: Verificación cruzada final
            final_score = score_percentage
            final_is_correct = is_correct
            
            if final_is_correct and final_score < min_score:
                print(f"   ⚠️ CAPA 4: Inconsistencia detectada - is_correct={final_is_correct} pero score={final_score}%")
                print(f"   ✅ CORRECCIÓN: Ajustando a {min_score}%")
                final_score = min_score
                evaluation['score_percentage'] = min_score
            
            if all_tests_passed and final_score < min_score:
                print(f"   ⚠️ CAPA 4: Inconsistencia detectada - todos tests OK pero score={final_score}%")
                print(f"   ✅ CORRECCIÓN: Ajustando a {min_score}%")
                final_score = min_score
                final_is_correct = True
                evaluation['score_percentage'] = min_score
                evaluation['is_correct'] = True
            
            # 🔴 CAPA 5: GARANTÍA ABSOLUTA - última verificación antes de guardar
            if evaluation.get('is_correct', False) or all_tests_passed:
                if final_score < min_score:
                    print(f"   🚨 CAPA 5 - GARANTÍA ABSOLUTA:")
                    print(f"   ⚠️ Score final {final_score}% es menor que mínimo {min_score}%")
                    print(f"   ✅ FORZANDO score a {min_score}% (ÚLTIMA VERIFICACIÓN)")
                    final_score = min_score
                    final_is_correct = True
                    evaluation['score_percentage'] = min_score
                    evaluation['is_correct'] = True
            
            print(f"   ✅ Score final después de validaciones: {final_score}%")
            print(f"   ✅ is_correct final: {final_is_correct}\n")
            
            # Actualizar respuesta con evaluación VALIDADA
            answer.is_correct = final_is_correct
            answer.points_earned = (final_score / 100) * answer.question.points
            answer.feedback = evaluation.get('feedback', '')
            answer.test_results = evaluation.get('test_results', {})
            answer.save()
            
            serializer = self.get_serializer(answer)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': f'Error al evaluar código: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def evaluate_code_sandbox(self, request, pk=None):
        """
        Evalúa código usando resultados de sandbox + IA para calidad
        POST /api/assessments/answers/{id}/evaluate_code_sandbox/

        Body esperado:
        {
            "test_results": [
                {
                    "test_case": "Test 1",
                    "input": "[1,2,3]",
                    "expected_output": "6",
                    "actual_output": "6",
                    "passed": true,
                    "execution_time_ms": 1.23,
                    "error": null
                }
            ],
            "total_tests": 3,
            "passed_tests": 2,
            "sandbox_success": true
        }
        """
        answer = self.get_object()

        # Obtener datos del sandbox
        test_results = request.data.get('test_results', [])
        total_tests = request.data.get('total_tests', 0)
        passed_tests = request.data.get('passed_tests', 0)
        sandbox_success = request.data.get('sandbox_success', False)
        use_backend_execution = request.data.get('use_backend_execution', False)
        
        # 🐍 Si el frontend solicita ejecución en backend (Python/Java)
        if use_backend_execution:
            programming_language = request.data.get('programming_language', 'python')
            test_cases = request.data.get('test_cases', [])
            code = request.data.get('code', answer.code_answer)
            
            print(f"\n🐍 EJECUTANDO CÓDIGO EN BACKEND ({programming_language.upper()})")
            print(f"   Código a ejecutar: {code[:100]}...")
            print(f"   Test cases: {len(test_cases)}")
            
            # Ejecutar código con Piston API
            import requests
            
            test_results = []
            passed_tests = 0
            
            # Mapeo de lenguajes a Piston
            language_map = {
                'python': 'python',
                'javascript': 'javascript',
                'java': 'java'
            }
            
            piston_language = language_map.get(programming_language.lower(), 'python')
            
            for idx, test_case in enumerate(test_cases, 1):
                test_input = test_case.get('input', '')
                expected_output = test_case.get('expected_output', '')
                description = test_case.get('description', f'Test {idx}')
                
                print(f"\n🔍 DEBUG Test {idx}:")
                print(f"   Input original: {repr(test_input)} (tipo: {type(test_input)})")
                print(f"   Expected output: {repr(expected_output)}")
                
                # Parsear el input - puede venir como array ["value"] o valor directo
                # Si viene como ["value"], extraer solo el valor
                try:
                    import ast
                    parsed_input = ast.literal_eval(test_input)
                    print(f"   Parsed con ast.literal_eval: {parsed_input} (tipo: {type(parsed_input)})")
                    # Si es una lista de un solo elemento, extraerlo
                    if isinstance(parsed_input, list) and len(parsed_input) == 1:
                        actual_input = parsed_input[0]
                    elif isinstance(parsed_input, list):
                        # Si es lista de múltiples elementos, mantenerlo como lista
                        actual_input = parsed_input
                    else:
                        actual_input = parsed_input
                except Exception as e:
                    # Si falla el parsing, usar el input tal cual
                    print(f"   ⚠️ Error parseando: {e}")
                    actual_input = test_input
                
                print(f"   Actual input: {actual_input} (tipo: {type(actual_input)})")
                
                print(f"   Actual input: {actual_input} (tipo: {type(actual_input)})")
                
                # Construir código con test case
                if programming_language.lower() == 'python':
                    test_input_formatted = repr(actual_input)
                    test_code = f"""{code}

# Test case {idx}
result = solution({test_input_formatted})
print(result)
"""
                elif programming_language.lower() == 'javascript':
                    # Para JavaScript, convertir a sintaxis JS válida
                    test_input_formatted = json.dumps(actual_input)
                    print(f"   Input formateado para JS: {test_input_formatted}")
                    test_code = f"""{code}

// Test case {idx}
const result = solution({test_input_formatted});
console.log(result);
"""
                    print(f"   Código a ejecutar:\n{test_code[:200]}...")
                else:
                    test_input_formatted = str(actual_input)
                    test_code = code  # Para otros lenguajes, ajustar según sea necesario
                
                try:
                    # Llamar a Piston API
                    piston_response = requests.post(
                        'https://emkc.org/api/v2/piston/execute',
                        json={
                            'language': piston_language,
                            'version': '*',
                            'files': [{
                                'content': test_code
                            }]
                        },
                        timeout=10
                    )
                    
                    piston_result = piston_response.json()
                    actual_output = piston_result.get('run', {}).get('output', '').strip()
                    error = piston_result.get('run', {}).get('stderr', '')
                    
                    # Comparar resultado - normalizar valores null/None
                    # Para JavaScript: null, undefined -> normalizar
                    # Para Python: None -> normalizar
                    def normalize_output(val):
                        val_str = str(val).strip().strip('"')
                        if val_str.lower() in ['null', 'none', 'undefined']:
                            return 'null'
                        return val_str
                    
                    passed = normalize_output(actual_output) == normalize_output(expected_output)
                    
                    if passed:
                        passed_tests += 1
                    
                    test_results.append({
                        'test_case': description,
                        'input': test_input,
                        'expected_output': expected_output,
                        'actual_output': actual_output if not error else None,
                        'passed': passed,
                        'execution_time_ms': 0,
                        'error': error if error else None
                    })
                    
                    print(f"   ✅ Test {idx}: {'PASÓ' if passed else 'FALLÓ'}")
                    
                except Exception as e:
                    print(f"   ❌ Error ejecutando test {idx}: {e}")
                    test_results.append({
                        'test_case': description,
                        'input': test_input,
                        'expected_output': expected_output,
                        'actual_output': None,
                        'passed': False,
                        'execution_time_ms': 0,
                        'error': str(e)
                    })
            
            total_tests = len(test_cases)
            sandbox_success = True
            
            print(f"   📊 Resultado final: {passed_tests}/{total_tests} tests pasados\n")

        if not sandbox_success or total_tests == 0:
            # Si el sandbox falló, usar evaluación tradicional con IA
            return self.evaluate_code(request, pk)

        # CALCULAR SCORE BASADO EN TESTS (70% funcionalidad)
        functionality_score = (passed_tests / total_tests) * 70

        # Determinar si el código es correcto (pasa todos los tests)
        is_correct = passed_tests == total_tests

        # USAR IA SOLO PARA EVALUAR CALIDAD (30%)
        quality_score = 0
        ai_quality_feedback = ""

        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            # Prompt simplificado - SOLO calidad, NO funcionalidad
            quality_prompt = f"""Evalúa SOLO la CALIDAD del siguiente código.

NO evalúes si funciona (ya se probó con tests reales).
Solo evalúa:
1. Legibilidad (¿es fácil de entender?)
2. Eficiencia (¿usa buen algoritmo?)
3. Buenas prácticas (¿sigue convenciones?)

Da un puntaje de 0-30 (30 = excelente calidad).

Código:
```
{answer.code_answer}
```

Responde en JSON:
{{
    "quality_score": <número 0-30>,
    "quality_feedback": "<feedback breve sobre calidad>",
    "strengths": ["punto fuerte 1", "punto fuerte 2"],
    "improvements": ["sugerencia 1", "sugerencia 2"]
}}
"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un evaluador experto de calidad de código."},
                    {"role": "user", "content": quality_prompt}
                ],
                temperature=0.6,
                response_format={"type": "json_object"}
            )

            quality_result = json.loads(response.choices[0].message.content)
            quality_score = quality_result.get('quality_score', 15)
            ai_quality_feedback = quality_result.get('quality_feedback', '')

        except Exception as e:
            logger.error(f"Error al evaluar calidad con IA: {e}")
            # Si falla IA, dar puntaje promedio de calidad
            quality_score = 15 if is_correct else 10
            ai_quality_feedback = "Calidad no evaluada por IA (error técnico)."

        # SCORE FINAL = Funcionalidad (tests) + Calidad (IA)
        final_score = functionality_score + quality_score

        # Garantizar mínimos
        if is_correct and final_score < 70:
            final_score = 70  # Mínimo 70% si pasa todos los tests

        # Generar feedback combinado
        feedback_parts = []

        # 1. Resultados de tests
        feedback_parts.append(f"🔒 **Evaluación con Sandbox (ejecución real)**\n")
        feedback_parts.append(f"✅ Tests pasados: {passed_tests}/{total_tests}\n\n")

        for idx, test in enumerate(test_results, 1):
            icon = "✅" if test.get('passed') else "❌"
            feedback_parts.append(f"{icon} Test {idx}: {test.get('test_case', f'Test {idx}')}\n")
            feedback_parts.append(f"   Input: {test.get('input')}\n")
            feedback_parts.append(f"   Esperado: {test.get('expected_output')}\n")
            feedback_parts.append(f"   Obtenido: {test.get('actual_output')}\n")
            if test.get('error'):
                feedback_parts.append(f"   Error: {test.get('error')}\n")
            feedback_parts.append("\n")

        # 2. Evaluación de calidad por IA
        if ai_quality_feedback:
            feedback_parts.append(f"\n🤖 **Evaluación de Calidad (IA)**\n")
            feedback_parts.append(f"{ai_quality_feedback}\n")

        # 3. Resumen
        if is_correct:
            feedback_parts.append(f"\n🎉 **¡Excelente!** Tu código pasó todos los tests.\n")
        else:
            feedback_parts.append(f"\n⚠️ **Atención:** Tu código no pasó todos los tests.\n")

        feedback_parts.append(f"\n📊 **Desglose de puntaje:**\n")
        feedback_parts.append(f"- Funcionalidad (tests): {functionality_score:.1f}/70\n")
        feedback_parts.append(f"- Calidad (código): {quality_score:.1f}/30\n")
        feedback_parts.append(f"- **Total: {final_score:.1f}/100**\n")

        combined_feedback = "".join(feedback_parts)

        # Actualizar respuesta
        answer.is_correct = is_correct
        answer.points_earned = round(final_score)
        answer.feedback = combined_feedback
        answer.test_results = test_results  # Guardar los resultados de los tests
        answer.save()

        # Serializar y retornar
        serializer = self.get_serializer(answer)
        return Response(serializer.data)
