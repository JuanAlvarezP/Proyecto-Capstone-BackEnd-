from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.conf import settings
import json
import logging
from .models import Assessment, Question, CandidateAnswer
from .serializers import (
    AssessmentListSerializer, AssessmentDetailSerializer, AssessmentCreateSerializer,
    QuestionSerializer, QuestionCreateSerializer, CandidateAnswerSerializer
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
                    correct_index = int(question.correct_answer) if question.correct_answer.isdigit() else -1
                    is_correct = answer.selected_option_index == correct_index
                
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
            
            # Validación adicional: si todos los tests pasaron, asegurar puntaje mínimo
            test_results = evaluation.get('test_results', [])
            if test_results:
                all_passed = all(t.get('passed', False) for t in test_results)
                if all_passed:
                    # Puntajes mínimos por dificultad cuando TODOS los tests pasan
                    min_scores = {'EASY': 80, 'MEDIUM': 75, 'HARD': 70}
                    min_score = min_scores.get(difficulty, 75)
                    
                    if score_percentage < min_score:
                        score_percentage = min_score
                        evaluation['score_percentage'] = min_score
                        evaluation['feedback'] = f"✅ TODOS los tests pasaron correctamente. {evaluation.get('feedback', '')}"
            
            # Actualizar respuesta con evaluación
            answer.is_correct = evaluation.get('is_correct', False)
            answer.points_earned = (score_percentage / 100) * answer.question.points
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
