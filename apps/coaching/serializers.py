from rest_framework import serializers
from .models import CoachProfile, AvailabilitySlot, Appointment
from users.models import User

class AvailabilitySlotSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = AvailabilitySlot
        fields = ['id', 'coach', 'day_of_week', 'day_name', 'start_time', 'end_time', 'is_active']
        read_only_fields = ['coach']


class CoachUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


class CoachProfileSerializer(serializers.ModelSerializer):
    user_details = CoachUserSerializer(source='user', read_only=True)
    availability_slots = AvailabilitySlotSerializer(many=True, read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = CoachProfile
        fields = [
            'id', 'user', 'user_details', 'full_name', 'title', 'bio', 
            'specialties', 'years_of_experience', 'denomination', 
            'hourly_rate', 'languages', 'avatar_url', 'is_verified', 
            'rating', 'reviews_count', 'meeting_link', 
            'availability_description', 'availability_slots'
        ]
        read_only_fields = ['user', 'rating', 'reviews_count']

    def get_full_name(self, obj):
        name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return name if name else obj.user.username


class AppointmentSerializer(serializers.ModelSerializer):
    coach_title = serializers.CharField(source='coach.title', read_only=True)
    coach_name = serializers.SerializerMethodField()
    coach_avatar = serializers.CharField(source='coach.avatar_url', read_only=True)
    user_name = serializers.SerializerMethodField()
    session_type_display = serializers.CharField(source='get_session_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'coach', 'coach_title', 'coach_name', 'coach_avatar',
            'user', 'user_name', 'appointment_date', 'duration_minutes',
            'session_type', 'session_type_display', 'status', 'status_display',
            'meeting_link', 'user_notes', 'pastoral_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_coach_name(self, obj):
        name = f"{obj.coach.user.first_name} {obj.coach.user.last_name}".strip()
        return name if name else obj.coach.user.username

    def get_user_name(self, obj):
        name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return name if name else obj.user.username
