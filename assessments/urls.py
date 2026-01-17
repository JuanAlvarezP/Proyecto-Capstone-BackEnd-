from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssessmentViewSet, QuestionViewSet, CandidateAnswerViewSet

router = DefaultRouter()
router.register(r'assessments', AssessmentViewSet, basename='assessment')
router.register(r'questions', QuestionViewSet, basename='question')
router.register(r'answers', CandidateAnswerViewSet, basename='answer')

urlpatterns = [
    # Ruta especial para análisis de aplicación con ID en URL
    path('analyze-application/<int:app_id>/', 
         AssessmentViewSet.as_view({'post': 'analyze_application_url'}), 
         name='analyze-application-url'),
    path('', include(router.urls)),
]

