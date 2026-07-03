from rest_framework import serializers
from .models import Match, Message
from users.models import User

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'

class UserChatSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    denomination = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email', 'avatar', 'denomination')

    def get_avatar(self, obj):
        if hasattr(obj, 'profile') and obj.profile.avatar:
            # En Django Cloudinary Storage, obj.profile.avatar.url retourne l'URL cloudinary absolue
            return obj.profile.avatar.url
        return None

    def get_denomination(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.denomination
        return None

class MatchSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    user1_details = UserChatSerializer(source='user1', read_only=True)
    user2_details = UserChatSerializer(source='user2', read_only=True)

    class Meta:
        model = Match
        fields = ('id', 'user1', 'user2', 'is_accepted', 'created_at', 'messages', 'user1_details', 'user2_details')


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
    # Pour M2M on peut vouloir envoyer/recevoir une liste d'IDs
    preferred_languages = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    
    class Meta:
        model = MatchPreferences
        fields = [
            'preferred_age_min', 'preferred_age_max', 'preferred_distance',
            'preferred_country', 'preferred_languages', 'preferred_denominations',
            'deal_breakers'
        ]
