from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Application
from .serializers import ApplicationSerializer
from .utils import extract_text, compute_match, compute_match_v2
from .ai_client import parse_cv_text


class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.select_related("candidate", "project").all().order_by("-created_at")
    serializer_class = ApplicationSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # Añadido JSONParser
    permission_classes = [permissions.IsAuthenticated]

    # Si no eres admin (is_staff), solo ves tus propias aplicaciones
    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(candidate=self.request.user)
        return qs

    def perform_create(self, serializer):
        # Procesamiento de CV con IA (código de tu compañero)
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

    # Endpoint personalizado para actualizar el estado (solo admin)
    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAdminUser])
    def update_status(self, request, pk=None):
        """
        Endpoint para que los admins actualicen el estado de una aplicación.
        PATCH /api/recruiting/applications/{id}/update_status/
        Body: {"status": "REVIEW"}
        """
        application = self.get_object()
        new_status = request.data.get('status')
        
        # Validar que el estado sea válido
        valid_statuses = [choice[0] for choice in Application.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {'error': f'Estado inválido. Opciones: {valid_statuses}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        application.status = new_status
        application.save()
        
        serializer = self.get_serializer(application)
        return Response(serializer.data)

    # Permitir que admins actualicen el estado mediante PATCH normal
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Si el usuario es admin, permitir actualizar el status
        if request.user.is_staff and 'status' in request.data:
            # Validar que el estado sea válido
            new_status = request.data.get('status')
            valid_statuses = [choice[0] for choice in Application.STATUS_CHOICES]
            
            if new_status not in valid_statuses:
                return Response(
                    {'error': f'Estado inválido. Opciones: {valid_statuses}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            instance.status = new_status
            instance.save()
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
