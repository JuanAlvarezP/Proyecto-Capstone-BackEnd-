from django.db import models
from django.contrib.auth.models import User
from projects.models import Project
from django.db.models import JSONField


class Assessment(models.Model):
    """Prueba técnica o práctica asignada a un candidato"""
    
    TYPE_CHOICES = [
        ("QUIZ", "Cuestionario Técnico"),
        ("CODING", "Prueba Práctica de Código"),
    ]
    
    DIFFICULTY_CHOICES = [
        ("EASY", "Fácil"),
        ("MEDIUM", "Medio"),
        ("HARD", "Difícil"),
    ]
    
    STATUS_CHOICES = [
        ("PENDING", "Pendiente"),
        ("IN_PROGRESS", "En Progreso"),
        ("COMPLETED", "Completada"),
        ("EVALUATED", "Evaluada"),
    ]
    
    candidate = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assessments")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="assessments")
    assessment_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default="MEDIUM")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    time_limit_minutes = models.IntegerField(default=60, help_text="Tiempo límite en minutos")
    passing_score = models.FloatField(default=70.0, help_text="Porcentaje mínimo para aprobar")
    
    # Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    score = models.FloatField(null=True, blank=True, help_text="Puntuación final (0-100)")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["candidate", "status"]),
            models.Index(fields=["project"]),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.candidate.username} ({self.get_assessment_type_display()})"


class Question(models.Model):
    """Pregunta individual dentro de una prueba"""
    
    TYPE_CHOICES = [
        ("MULTIPLE_CHOICE", "Opción Múltiple"),
        ("TRUE_FALSE", "Verdadero/Falso"),
        ("CODE", "Código (Editor Monaco)"),
        ("SHORT_ANSWER", "Respuesta Corta"),
    ]
    
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="questions")
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    question_text = models.TextField(help_text="Texto de la pregunta")
    code_snippet = models.TextField(blank=True, help_text="Código de ejemplo o plantilla inicial")
    
    # Para preguntas de opción múltiple
    options = JSONField(default=list, blank=True, help_text="Array de opciones: ['Opción A', 'Opción B', ...]")
    correct_answer = models.TextField(blank=True, help_text="Respuesta correcta o índice de opción correcta")
    
    # Para preguntas de código
    programming_language = models.CharField(max_length=50, blank=True, help_text="python, javascript, java, etc.")
    test_cases = JSONField(default=list, blank=True, help_text="Casos de prueba para validar código")
    
    # Metadata
    points = models.FloatField(default=10.0, help_text="Puntos que vale esta pregunta")
    order = models.IntegerField(default=0, help_text="Orden de aparición")
    explanation = models.TextField(blank=True, help_text="Explicación de la respuesta correcta")
    
    # Generado por IA
    generated_by_ai = models.BooleanField(default=False)
    ai_prompt = models.TextField(blank=True, help_text="Prompt usado para generar la pregunta")
    
    class Meta:
        ordering = ["assessment", "order"]
        indexes = [
            models.Index(fields=["assessment", "order"]),
        ]
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."


class CandidateAnswer(models.Model):
    """Respuesta de un candidato a una pregunta específica"""
    
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="candidate_answers")
    candidate = models.ForeignKey(User, on_delete=models.CASCADE, related_name="answers")
    
    # Respuesta
    answer_text = models.TextField(blank=True, help_text="Respuesta de texto o código")
    selected_option_index = models.IntegerField(null=True, blank=True, help_text="Índice de opción seleccionada (para multiple choice)")
    
    # Evaluación
    is_correct = models.BooleanField(null=True, blank=True)
    points_earned = models.FloatField(default=0.0)
    feedback = models.TextField(blank=True, help_text="Retroalimentación del evaluador o IA")
    
    # Metadata
    answered_at = models.DateTimeField(auto_now_add=True)
    time_spent_seconds = models.IntegerField(default=0, help_text="Tiempo que tomó responder")
    
    # Ejecución de código
    code_output = models.TextField(blank=True, help_text="Salida del código ejecutado")
    test_results = JSONField(default=dict, blank=True, help_text="Resultados de test cases")
    
    class Meta:
        unique_together = ("question", "candidate")
        ordering = ["-answered_at"]
        indexes = [
            models.Index(fields=["candidate", "question"]),
        ]
    
    def __str__(self):
        return f"{self.candidate.username} - {self.question.question_text[:30]}..."
