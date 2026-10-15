from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MatchViewSet, MessageViewSet, CallSessionViewSet, 
    SuggestionView, SwipeActionView, MapSearchProfileView
)

router = DefaultRouter()
router.register('matches', MatchViewSet, basename='match')
router.register('messages', MessageViewSet, basename='message')
router.register('calls', CallSessionViewSet, basename='call')

urlpatterns = [
    path('suggestions/', SuggestionView.as_view(), name='match-suggestions'),
    path('action/', SwipeActionView.as_view(), name='match-action'),
    path('map-search/', MapSearchProfileView.as_view(), name='map-search'),
    path('', include(router.urls)),
]

