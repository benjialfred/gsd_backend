from rest_framework import serializers
from .models import Event, TicketTier, EventRegistration


class TicketTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketTier
        fields = [
            'id', 'event', 'name', 'description', 
            'price', 'capacity', 'available_quantity', 'is_active'
        ]


class EventSerializer(serializers.ModelSerializer):
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    ticket_tiers = TicketTierSerializer(many=True, read_only=True)
    min_price = serializers.SerializerMethodField()
    available_spots = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'event_type', 'event_type_display', 
            'description', 'theme_verse', 'dress_code', 'banner_image', 
            'location_name', 'city', 'address', 'is_online', 
            'online_meeting_link', 'start_date', 'end_date', 'capacity', 
            'is_published', 'is_featured', 'ticket_tiers', 'min_price', 
            'available_spots', 'created_at', 'updated_at'
        ]

    def get_min_price(self, obj):
        active_tiers = obj.ticket_tiers.filter(is_active=True)
        if active_tiers.exists():
            return min(tier.price for tier in active_tiers)
        return 0.00

    def get_available_spots(self, obj):
        active_tiers = obj.ticket_tiers.filter(is_active=True)
        return sum(tier.available_quantity for tier in active_tiers)


class EventRegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)
    event_banner = serializers.CharField(source='event.banner_image', read_only=True)
    event_date = serializers.DateTimeField(source='event.start_date', read_only=True)
    event_location = serializers.CharField(source='event.location_name', read_only=True)
    event_city = serializers.CharField(source='event.city', read_only=True)
    dress_code = serializers.CharField(source='event.dress_code', read_only=True)
    
    ticket_name = serializers.CharField(source='ticket_tier.name', read_only=True)
    ticket_price = serializers.DecimalField(source='ticket_tier.price', max_digits=10, decimal_places=2, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = EventRegistration
        fields = [
            'id', 'event', 'event_title', 'event_banner', 'event_date', 
            'event_location', 'event_city', 'dress_code',
            'ticket_tier', 'ticket_name', 'ticket_price',
            'user', 'guest_name', 'guest_email', 'guest_phone', 
            'qr_code_hash', 'status', 'status_display',
            'is_checked_in', 'checked_in_at', 'created_at'
        ]
        read_only_fields = ['user', 'qr_code_hash', 'is_checked_in', 'checked_in_at', 'created_at']
