from django.urls import path
from .views import ActivityFeedView, EventTrackView

urlpatterns = [
    path('feed/', ActivityFeedView.as_view(), name='activity-feed'),
    path('events/', EventTrackView.as_view(), name='event-track'),
]
