from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet
from projects.views import MeetingViewSet


router = DefaultRouter()
router.register(r"", ProjectViewSet, basename="project")
router.register(r"meetings", MeetingViewSet, basename="meeting")

urlpatterns = [
    path("", include(router.urls)),

]
