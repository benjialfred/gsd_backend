from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, GoogleLoginView, RegisterView, VerifyEmailView

router = DefaultRouter()
router.register('', UserViewSet)

urlpatterns = [
    path('google/', GoogleLoginView.as_view(), name='google-login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('verify/', VerifyEmailView.as_view(), name='verify-email'),
    path('', include(router.urls)),
]

