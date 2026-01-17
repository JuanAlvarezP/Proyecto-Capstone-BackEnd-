from rest_framework import serializers
from .models import Assessment, Question, CandidateAnswer
from django.contrib.auth.models import User


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer para preguntas - incluye correct_answer para evaluación"""
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'question_text', 'code_snippet',
            'options', 'correct_answer', 'programming_language', 'points', 'order',
            'generated_by_ai', 'test_cases'
        ]
        # correct_answer es necesario para que el frontend valide respuestas de quiz
        # test_cases es necesario para sandbox
        # No exponer: explanation, ai_prompt (solo para admins)
        
    def to_representation(self, instance):
        """Personalizar la respuesta según el tipo de usuario"""
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        # Si es admin, mostrar también las respuestas correctas
        if request and request.user.is_staff:
            data['correct_answer'] = instance.correct_answer
            data['explanation'] = instance.explanation
            data['ai_prompt'] = instance.ai_prompt
            
        return data


class QuestionCreateSerializer(serializers.ModelSerializer):
    """Serializer completo para crear/editar preguntas (solo admin)"""
    
    class Meta:
        model = Question
        fields = '__all__'


class CandidateAnswerSerializer(serializers.ModelSerializer):
    """Serializer para respuestas de candidatos"""
    question = QuestionSerializer(read_only=True)  # Para lectura - objeto completo
    question_id = serializers.IntegerField(write_only=True)  # Para escritura - solo ID
    score_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = CandidateAnswer
        fields = [
            'id', 'question', 'question_id', 'answer_text', 'selected_option_index', 'code_answer',
            'is_correct', 'points_earned', 'score_percentage', 'feedback', 'answered_at',
            'time_spent_seconds', 'code_output', 'test_results'
        ]
        read_only_fields = ['is_correct', 'points_earned', 'feedback', 'code_output', 'test_results']
    
    def get_score_percentage(self, obj):
        """Calcula el porcentaje de puntos obtenidos"""
        if obj.question and obj.question.points > 0:
            return round((obj.points_earned / obj.question.points) * 100, 1)
        return 0.0


class AssessmentListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listar pruebas"""
    candidate_username = serializers.ReadOnlyField(source='candidate.username')
    project_title = serializers.ReadOnlyField(source='project.title')
    question_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Assessment
        fields = [
            'id', 'candidate', 'candidate_username', 'project', 'project_title',
            'assessment_type', 'difficulty', 'title', 'status', 'score',
            'time_limit_minutes', 'passing_score', 'question_count',
            'started_at', 'completed_at', 'created_at'
        ]
        
    def get_question_count(self, obj):
        return obj.questions.count()


class AssessmentDetailSerializer(serializers.ModelSerializer):
    """Serializer completo con preguntas incluidas"""
    candidate_username = serializers.ReadOnlyField(source='candidate.username')
    candidate_email = serializers.ReadOnlyField(source='candidate.email')
    project_title = serializers.ReadOnlyField(source='project.title')
    questions = QuestionSerializer(many=True, read_only=True)
    total_points = serializers.SerializerMethodField()
    
    class Meta:
        model = Assessment
        fields = [
            'id', 'candidate', 'candidate_username', 'candidate_email',
            'project', 'project_title', 'assessment_type', 'difficulty',
            'title', 'description', 'status', 'score', 'time_limit_minutes',
            'passing_score', 'started_at', 'completed_at', 'created_at',
            'updated_at', 'questions', 'total_points'
        ]
        read_only_fields = ['score', 'started_at', 'completed_at']
        
    def get_total_points(self, obj):
        return sum(q.points for q in obj.questions.all())


class AssessmentCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear nuevas pruebas"""
    
    class Meta:
        model = Assessment
        fields = [
            'id', 'candidate', 'project', 'assessment_type', 'difficulty',
            'title', 'description', 'time_limit_minutes', 'passing_score',
            'status', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'created_at']


class ApplicationAnalysisInputSerializer(serializers.Serializer):
    """Serializer para validar input del análisis de aplicación"""
    application_id = serializers.IntegerField(required=True, help_text="ID de la aplicación a analizar")


class ApplicationAnalysisOutputSerializer(serializers.Serializer):
    """Serializer para la respuesta del análisis de aplicación"""
    suggested_title = serializers.CharField(max_length=200)
    suggested_description = serializers.CharField(max_length=500)
    suggested_type = serializers.ChoiceField(choices=['QUIZ', 'CODING'])
    suggested_difficulty = serializers.ChoiceField(choices=['EASY', 'MEDIUM', 'HARD'])
    suggested_time_minutes = serializers.IntegerField(min_value=15, max_value=180)
    suggested_passing_score = serializers.FloatField(min_value=50, max_value=100)
    suggested_num_questions = serializers.IntegerField(min_value=1, max_value=20)
    suggested_programming_language = serializers.CharField(max_length=50, allow_null=True, required=False)
    
    # Razones del análisis
    difficulty_reason = serializers.CharField()
    time_reason = serializers.CharField()
    score_reason = serializers.CharField()
    type_reason = serializers.CharField()
    
    # Metadata del análisis
    detected_skills = serializers.ListField(child=serializers.CharField())
    candidate_experience_level = serializers.ChoiceField(choices=['junior', 'intermediate', 'senior'])
    project_complexity = serializers.ChoiceField(choices=['low', 'medium', 'high'])
    
    # Info adicional
    application_id = serializers.IntegerField()
    analyzed_at = serializers.CharField()
    fallback_used = serializers.BooleanField(default=False, required=False)

