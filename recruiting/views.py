from rest_framework import viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Application
from .serializers import ApplicationSerializer
from .utils import extract_text, compute_match, compute_match_v2
from .ai_client import parse_cv_text


class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.select_related("candidate", "project").all().order_by("-created_at")
    serializer_class = ApplicationSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    # Si no eres admin (is_staff), solo ves tus propias aplicaciones
    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(candidate=self.request.user)
        return qs

    def perform_create(self, serializer):
        app = serializer.save(candidate=self.request.user)

        # 1. EXTRAER TEXTO DEL ARCHIVO
        if app.cv_file:
            text = extract_text(app.cv_file.path)
            app.parsed_text = text[:20000]

        # 2. ENVIAR A IA PARA JSON
        extracted = {}
        if app.parsed_text:
            try:
                extracted = parse_cv_text(app.parsed_text)
            except Exception as e:
                extracted = {"error": str(e)}

        app.extracted = extracted

        # 3. CALCULAR MATCH SCORE


        req = list(app.project.required_skills or [])
        candidate_hard = (extracted.get("skills", {}) or {}).get("hard", [])

        app.match_score = compute_match_v2(req, candidate_hard)


        app.save()