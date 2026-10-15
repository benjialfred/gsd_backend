from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, GoogleLoginView, RegisterView, VerifyEmailView, 
    PasswordResetRequestView, PasswordResetConfirmView,
    SetPinView, RemovePinView, PinLoginView
)

router = DefaultRouter()
router.register('', UserViewSet)

urlpatterns = [
    path('google/', GoogleLoginView.as_view(), name='google-login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('verify/', VerifyEmailView.as_view(), name='verify-email'),
    path('set-pin/', SetPinView.as_view(), name='set-pin'),
    path('remove-pin/', RemovePinView.as_view(), name='remove-pin'),
    path('pin-login/', PinLoginView.as_view(), name='pin-login'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('', include(router.urls)),
]

