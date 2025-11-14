from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssessmentViewSet, QuestionViewSet, CandidateAnswerViewSet

router = DefaultRouter()
router.register(r'assessments', AssessmentViewSet, basename='assessment')
router.register(r'questions', QuestionViewSet, basename='question')
router.register(r'answers', CandidateAnswerViewSet, basename='answer')

urlpatterns = [
    path('', include(router.urls)),
]
