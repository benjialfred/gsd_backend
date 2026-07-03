from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MatchViewSet, MessageViewSet, SuggestionView, SwipeActionView

router = DefaultRouter()
router.register('matches', MatchViewSet, basename='match')
router.register('messages', MessageViewSet, basename='message')

urlpatterns = [
    path('suggestions/', SuggestionView.as_view(), name='match-suggestions'),
    path('action/', SwipeActionView.as_view(), name='match-action'),
    path('', include(router.urls)),
]
