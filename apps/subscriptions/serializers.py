from rest_framework import serializers
from .models import SubscriptionPlan, UserSubscription


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'code', 'billing_cycle', 'price', 
            'duration_days', 'badge_name', 'badge_color', 
            'description', 'features', 'daily_likes_limit', 
            'can_see_likes', 'can_call', 'can_use_audio_notes', 
            'has_academy_access', 'discount_percentage', 
            'is_featured', 'is_active', 'sort_order'
        ]


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionPlan.objects.all(), 
        source='plan', 
        write_only=True
    )
    is_valid = serializers.BooleanField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserSubscription
        fields = [
            'id', 'user', 'plan', 'plan_id', 'status', 
            'start_date', 'end_date', 'auto_renew', 
            'is_valid', 'days_remaining', 'last_payment_reference', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'status', 'start_date', 'end_date', 'last_payment_reference']
