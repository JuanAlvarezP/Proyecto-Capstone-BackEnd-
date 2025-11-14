from django.contrib import admin
from .models import Assessment, Question, CandidateAnswer


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ['order', 'question_type', 'question_text', 'points', 'generated_by_ai']
    readonly_fields = ['generated_by_ai']


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'candidate', 'project', 'assessment_type', 'difficulty', 'status', 'score', 'created_at']
    list_filter = ['assessment_type', 'difficulty', 'status', 'created_at']
    search_fields = ['title', 'candidate__username', 'project__title']
    readonly_fields = ['created_at', 'updated_at', 'started_at', 'completed_at']
    inlines = [QuestionInline]
    
    fieldsets = (
        ('Información General', {
            'fields': ('candidate', 'project', 'title', 'description')
        }),
        ('Configuración', {
            'fields': ('assessment_type', 'difficulty', 'time_limit_minutes', 'passing_score')
        }),
        ('Estado', {
            'fields': ('status', 'score', 'started_at', 'completed_at')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text_short', 'assessment', 'question_type', 'points', 'order', 'generated_by_ai']
    list_filter = ['question_type', 'generated_by_ai', 'assessment__assessment_type']
    search_fields = ['question_text', 'assessment__title']
    ordering = ['assessment', 'order']
    
    fieldsets = (
        ('Pregunta', {
            'fields': ('assessment', 'question_type', 'question_text', 'code_snippet', 'order')
        }),
        ('Opciones (Multiple Choice)', {
            'fields': ('options', 'correct_answer'),
            'classes': ('collapse',)
        }),
        ('Código', {
            'fields': ('programming_language', 'test_cases'),
            'classes': ('collapse',)
        }),
        ('Evaluación', {
            'fields': ('points', 'explanation')
        }),
        ('IA', {
            'fields': ('generated_by_ai', 'ai_prompt'),
            'classes': ('collapse',)
        }),
    )
    
    def question_text_short(self, obj):
        return obj.question_text[:60] + '...' if len(obj.question_text) > 60 else obj.question_text
    question_text_short.short_description = 'Pregunta'


@admin.register(CandidateAnswer)
class CandidateAnswerAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'question_short', 'is_correct', 'points_earned', 'answered_at']
    list_filter = ['is_correct', 'answered_at', 'question__question_type']
    search_fields = ['candidate__username', 'question__question_text', 'answer_text']
    readonly_fields = ['answered_at', 'test_results']
    
    fieldsets = (
        ('Información', {
            'fields': ('question', 'candidate')
        }),
        ('Respuesta', {
            'fields': ('answer_text', 'selected_option_index', 'time_spent_seconds')
        }),
        ('Evaluación', {
            'fields': ('is_correct', 'points_earned', 'feedback')
        }),
        ('Código', {
            'fields': ('code_output', 'test_results'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('answered_at',),
            'classes': ('collapse',)
        }),
    )
    
    def question_short(self, obj):
        return obj.question.question_text[:40] + '...' if len(obj.question.question_text) > 40 else obj.question.question_text
    question_short.short_description = 'Pregunta'
