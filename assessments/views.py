from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Assessment, Question, CandidateAnswer
from .serializers import (
    AssessmentListSerializer, AssessmentDetailSerializer, AssessmentCreateSerializer,
    QuestionSerializer, QuestionCreateSerializer, CandidateAnswerSerializer
)
from .openai_service import OpenAIAssessmentService


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
            "num_challenges": 3,  # Para CODING
            "language": "es"  # o "en"
        }
        """
        assessment = self.get_object()
        topic = request.data.get('topic')
        num_questions = request.data.get('num_questions', 10)
        num_challenges = request.data.get('num_challenges', 3)
        language = request.data.get('language', 'es')
        
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
                    language=language
                )
                
                for idx, q_data in enumerate(questions_data):
                    question = Question.objects.create(
                        assessment=assessment,
                        question_type=q_data.get('question_type', 'MULTIPLE_CHOICE'),
                        question_text=q_data['question_text'],
                        options=q_data.get('options', []),
                        correct_answer=str(q_data.get('correct_answer', '')),
                        explanation=q_data.get('explanation', ''),
                        points=q_data.get('points', 10),
                        order=idx,
                        generated_by_ai=True,
                        ai_prompt=f"Topic: {topic}, Difficulty: {assessment.difficulty}"
                    )
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
        
        serializer = self.get_serializer(assessment)
        return Response(serializer.data)


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
        """Filtrar según tipo de usuario"""
        qs = super().get_queryset()
        
        if not self.request.user.is_staff:
            # Candidatos solo ven sus propias respuestas
            qs = qs.filter(candidate=self.request.user)
            
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
            evaluation = ai_service.evaluate_code_answer(
                question_text=answer.question.question_text,
                candidate_code=answer.answer_text,
                test_cases=answer.question.test_cases,
                language=answer.question.programming_language
            )
            
            # Actualizar respuesta con evaluación
            answer.is_correct = evaluation.get('is_correct', False)
            answer.points_earned = (evaluation.get('score_percentage', 0) / 100) * answer.question.points
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
