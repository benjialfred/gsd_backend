from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from .models import UserJourneyEvent
from .serializers import UserJourneyEventSerializer

class ActivityFeedView(generics.ListAPIView):
    serializer_class = UserJourneyEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserJourneyEvent.objects.filter(user=self.request.user).order_by('-created_at')[:20]

class EventTrackView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        event_type = request.data.get('event_type')
        step = request.data.get('step')
        metadata = request.data.get('metadata', {})

        if not event_type:
            return Response({'error': 'event_type is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(metadata, dict):
            metadata = {}

        if step is not None:
            metadata['step'] = step

        event = UserJourneyEvent.objects.create(
            user=request.user,
            event_type=event_type,
            metadata=metadata
        )
        return Response({'status': 'ok', 'id': event.id}, status=status.HTTP_201_CREATED)
