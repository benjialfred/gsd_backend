from rest_framework import serializers
from .models import UserJourneyEvent

class UserJourneyEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserJourneyEvent
        fields = ['id', 'event_type', 'metadata', 'created_at']
