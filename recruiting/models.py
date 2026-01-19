from django.db import models
from django.contrib.auth.models import User
from projects.models import Project
from django.db.models import JSONField
from assessments.models import Assessment


def cv_upload_path(instance, filename):
    return f"cvs/user_{instance.candidate_id}/{filename}"

class Application(models.Model):
    STATUS_CHOICES = [
        ("SUBMITTED", "Submitted"),
        ("REVIEW", "In Review"),
        ("REJECTED", "Rejected"),
        ("APPROVED", "Approved"),
    ]

    candidate = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    cv_file = models.FileField(upload_to=cv_upload_path, blank=True, null=True)
    parsed_text = models.TextField(blank=True)
    extracted   = JSONField(default=dict, blank=True)  # ← IA: JSON estructurado
    match_score = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="SUBMITTED")
    created_at = models.DateTimeField(auto_now_add=True)
    ai_analysis = models.TextField(blank=True, null=True) #
    class Meta:
        unique_together = ("candidate", "project")  # 1 aplicación por proyecto

    def __str__(self):
        return f"{self.candidate.username} -> {self.project.title}"
