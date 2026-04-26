from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MatchViewSet, MessageViewSet

router = DefaultRouter()
router.register('matches', MatchViewSet, basename='match')
router.register('messages', MessageViewSet, basename='message')

urlpatterns = [
    path('', include(router.urls)),
]
