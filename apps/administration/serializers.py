from rest_framework import serializers
from users.models import User, UserProfile
from payments.models import PaymentTransaction
from events.models import Event, TicketTier, EventRegistration
from coaching.models import CoachProfile, Appointment
from profiles.models import KYCSubmission, KYCAuditLog
from analytics.models import UserJourneyEvent


class AdminUserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'id', 'gender', 'birth_date', 'denomination', 'church_attendance',
            'profession', 'education_level', 'marital_status', 'city', 'country_code',
            'latitude', 'longitude', 'onboarding_step', 'onboarding_completed', 'avatar'
        ]


class AdminUserSerializer(serializers.ModelSerializer):
    profile = AdminUserProfileSerializer(read_only=True)
    kyc_status = serializers.SerializerMethodField()
    has_active_subscription = serializers.SerializerMethodField()
    date_joined_formatted = serializers.DateTimeField(source='date_joined', format='%d/%m/%Y %H:%M', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'is_active', 'is_staff', 'is_superuser', 'email_verified',
            'date_joined', 'date_joined_formatted', 'profile', 'kyc_status',
            'has_active_subscription'
        ]

    def get_kyc_status(self, obj):
        if hasattr(obj, 'profile') and hasattr(obj.profile, 'kyc_submission'):
            return obj.profile.kyc_submission.status
        return 'NOT_SUBMITTED'

    def get_has_active_subscription(self, obj):
        if hasattr(obj, 'subscription'):
            return obj.subscription.status == 'ACTIVE'
        return False


class AdminTransactionSerializer(serializers.ModelSerializer):
    created_at_formatted = serializers.DateTimeField(source='created_at', format='%d/%m/%Y %H:%M', read_only=True)
    purpose_display = serializers.CharField(source='get_purpose_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'reference', 'nelsius_transaction_id', 'amount', 'currency',
            'payment_method', 'purpose', 'purpose_display', 'related_id',
            'status', 'status_display', 'checkout_url', 'customer_name',
            'customer_email', 'customer_phone', 'paid_at', 'created_at',
            'created_at_formatted'
        ]


class AdminTicketTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketTier
        fields = ['id', 'name', 'price', 'capacity', 'available_quantity', 'is_active']


class AdminEventSerializer(serializers.ModelSerializer):
    ticket_tiers = AdminTicketTierSerializer(many=True, read_only=True)
    registrations_count = serializers.SerializerMethodField()
    revenue_generated = serializers.SerializerMethodField()
    start_date_formatted = serializers.DateTimeField(source='start_date', format='%d/%m/%Y %H:%M', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'event_type', 'event_type_display',
            'description', 'theme_verse', 'dress_code', 'banner_image',
            'location_name', 'city', 'address', 'is_online', 'start_date',
            'start_date_formatted', 'end_date', 'capacity', 'is_published',
            'is_featured', 'ticket_tiers', 'registrations_count', 'revenue_generated'
        ]

    def get_registrations_count(self, obj):
        return obj.registrations.filter(status='CONFIRMED').count()

    def get_revenue_generated(self, obj):
        confirmed = obj.registrations.filter(status='CONFIRMED')
        return sum(reg.ticket_tier.price for reg in confirmed if reg.ticket_tier)


class AdminRegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)
    tier_name = serializers.CharField(source='ticket_tier.name', read_only=True)
    tier_price = serializers.DecimalField(source='ticket_tier.price', max_digits=10, decimal_places=2, read_only=True)
    created_at_formatted = serializers.DateTimeField(source='created_at', format='%d/%m/%Y %H:%M', read_only=True)

    class Meta:
        model = EventRegistration
        fields = [
            'id', 'event', 'event_title', 'ticket_tier', 'tier_name', 'tier_price',
            'guest_name', 'guest_email', 'guest_phone', 'qr_code_hash',
            'status', 'is_checked_in', 'checked_in_at', 'notes', 'created_at',
            'created_at_formatted'
        ]


class AdminAuditLogSerializer(serializers.ModelSerializer):
    admin_username = serializers.CharField(source='admin_user.username', read_only=True)
    target_user = serializers.CharField(source='submission.profile.user.username', read_only=True)
    created_at_formatted = serializers.DateTimeField(source='created_at', format='%d/%m/%Y %H:%M', read_only=True)

    class Meta:
        model = KYCAuditLog
        fields = ['id', 'action', 'admin_username', 'target_user', 'comments', 'created_at', 'created_at_formatted']


class AdminCoachSerializer(serializers.ModelSerializer):
    coach_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    appointments_count = serializers.SerializerMethodField()

    class Meta:
        model = CoachProfile
        fields = [
            'id', 'user_id', 'coach_name', 'email', 'title', 'denomination',
            'years_of_experience', 'hourly_rate', 'is_verified', 'rating',
            'reviews_count', 'appointments_count', 'avatar_url'
        ]

    def get_coach_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_appointments_count(self, obj):
        return obj.appointments.count()
