from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, GoogleLoginView

router = DefaultRouter()
router.register('', UserViewSet)

urlpatterns = [
    path('google/', GoogleLoginView.as_view(), name='google-login'),
    path('', include(router.urls)),
]
