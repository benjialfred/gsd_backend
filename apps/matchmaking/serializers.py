from rest_framework import serializers
from .models import Match, Message, UserReport, CallSession
from users.models import User

class MessageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ('id', 'match', 'sender', 'content', 'image', 'image_url', 'audio', 'audio_url', 'duration', 'reactions', 'is_deleted', 'timestamp', 'is_read')
        read_only_fields = ('sender', 'timestamp', 'is_read')

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    def get_audio_url(self, obj):
        if obj.audio:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.audio.url) if request else obj.audio.url
        return None


class UserChatSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    denomination = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email', 'avatar', 'denomination', 'city', 'age')

    def get_avatar(self, obj):
        request = self.context.get('request')
        if hasattr(obj, 'profile'):
            from profiles.models import ProfileMedia
            primary = ProfileMedia.objects.filter(profile=obj.profile, is_primary=True).first()
            if primary and primary.file:
                url = primary.file.url
                return request.build_absolute_uri(url) if request else url
            if obj.profile.avatar:
                url = obj.profile.avatar.url
                return request.build_absolute_uri(url) if request else url
        return None

    def get_denomination(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.denomination
        return None

    def get_city(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.city or obj.profile.country_code
        return None

    def get_age(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.age
        return None

class MatchSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    user1_details = UserChatSerializer(source='user1', read_only=True)
    user2_details = UserChatSerializer(source='user2', read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = (
            'id', 'user1', 'user2', 'is_accepted', 'conversation_id',
            'compatibility_score', 'compatibility_breakdown',
            'created_at', 'messages', 'user1_details', 'user2_details', 'last_message', 'unread_count'
        )

    def get_last_message(self, obj):
        last = obj.messages.order_by('-timestamp').first()
        if last:
            request = self.context.get('request')
            img_url = None
            if last.image:
                img_url = request.build_absolute_uri(last.image.url) if request else last.image.url
            audio_url = None
            if last.audio:
                audio_url = request.build_absolute_uri(last.audio.url) if request else last.audio.url
            return {
                'id': last.id,
                'content': last.content,
                'image_url': img_url,
                'audio_url': audio_url,
                'duration': last.duration,
                'sender': last.sender_id,
                'timestamp': last.timestamp,
                'is_read': last.is_read
            }
        return None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        return 0

class CallSessionSerializer(serializers.ModelSerializer):
    caller_details = UserChatSerializer(source='caller', read_only=True)
    receiver_details = UserChatSerializer(source='receiver', read_only=True)

    class Meta:
        model = CallSession
        fields = (
            'id', 'match', 'caller', 'caller_details', 
            'receiver', 'receiver_details', 'call_type', 
            'status', 'started_at', 'ended_at', 'duration_seconds'
        )
        read_only_fields = ('caller', 'started_at', 'ended_at', 'duration_seconds')

class UserReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserReport
        fields = ('id', 'reporter', 'reported_user', 'match', 'reason', 'details', 'created_at')
        read_only_fields = ('reporter', 'created_at')



from .models import MatchPreferences, UserDealBreaker, DealBreakerType

class UserDealBreakerSerializer(serializers.ModelSerializer):
    deal_breaker_type_code = serializers.CharField(source='deal_breaker_type.code', read_only=True)
    deal_breaker_type_id = serializers.PrimaryKeyRelatedField(
        queryset=DealBreakerType.objects.all(), source='deal_breaker_type', write_only=True
    )

    class Meta:
        model = UserDealBreaker
        fields = ['id', 'deal_breaker_type_code', 'deal_breaker_type_id', 'value']

class MatchPreferencesSerializer(serializers.ModelSerializer):
    deal_breakers = UserDealBreakerSerializer(many=True, read_only=True)
    preferred_languages = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    
    class Meta:
        model = MatchPreferences
        fields = [
            'preferred_age_min', 'preferred_age_max', 'preferred_distance',
            'preferred_country', 'preferred_languages', 'preferred_denominations',
            'deal_breakers'
        ]
