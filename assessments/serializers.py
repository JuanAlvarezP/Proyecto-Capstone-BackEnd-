from rest_framework import serializers
from .models import Assessment, Question, CandidateAnswer
from django.contrib.auth.models import User


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer para preguntas - oculta respuestas correctas al candidato"""
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'question_text', 'code_snippet',
            'options', 'programming_language', 'points', 'order',
            'generated_by_ai'
        ]
        # No exponer: correct_answer, test_cases, explanation, ai_prompt
        
    def to_representation(self, instance):
        """Personalizar la respuesta según el tipo de usuario"""
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        # Si es admin, mostrar también las respuestas correctas
        if request and request.user.is_staff:
            data['correct_answer'] = instance.correct_answer
            data['explanation'] = instance.explanation
            data['test_cases'] = instance.test_cases
            data['ai_prompt'] = instance.ai_prompt
            
        return data


class QuestionCreateSerializer(serializers.ModelSerializer):
    """Serializer completo para crear/editar preguntas (solo admin)"""
    
    class Meta:
        model = Question
        fields = '__all__'


class CandidateAnswerSerializer(serializers.ModelSerializer):
    """Serializer para respuestas de candidatos"""
    
    class Meta:
        model = CandidateAnswer
        fields = [
            'id', 'question', 'answer_text', 'selected_option_index',
            'is_correct', 'points_earned', 'feedback', 'answered_at',
            'time_spent_seconds', 'code_output', 'test_results'
        ]
        read_only_fields = ['is_correct', 'points_earned', 'feedback', 'code_output', 'test_results']


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
