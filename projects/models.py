from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Project(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    required_skills = models.JSONField(default=list)  # ["React","Django"]
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    priority = models.IntegerField(default=3)  # 1=alta ... 5=baja


class Meeting(models.Model):
    title = models.CharField(max_length=255)
    client_name = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    transcript_text = models.TextField(blank=True)

    # Tarifa / hora que usaremos para la cotización
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Resultado bruto de la IA (requerimientos, horas, costo, etc.)
    ai_result = models.JSONField(null=True, blank=True)

    # Proyecto creado automáticamente a partir de esta reunión
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.SET_NULL, related_name="meetings"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
