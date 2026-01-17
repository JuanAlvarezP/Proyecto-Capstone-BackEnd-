from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegisterView, MeView, UpdateMeView, ChangePasswordView, UserViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("me/update/",       UpdateMeView.as_view(), name="me-update"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("", include(router.urls)),
]