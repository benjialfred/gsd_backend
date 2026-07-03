from rest_framework import serializers
from .models import User, UserProfile

from profiles.services import ProfileCompletionService

class UserProfileSerializer(serializers.ModelSerializer):
    completion_percentage = serializers.SerializerMethodField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, write_only=True, required=False)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, write_only=True, required=False)
    kyc_status = serializers.CharField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'gender', 'birth_date', 'profession', 'education_level', 
            'denomination', 'church_attendance', 'spiritual_commitment',
            'marriage_objectives', 'marriage_values', 'marriage_expectations',
            'marital_status', 'bio', 'objectives', 'avatar',
            'country_code', 'latitude', 'longitude', 'location_visibility',
            'onboarding_completed', 'onboarding_step', 'kyc_status',
            'completion_percentage'
        ]

    def get_completion_percentage(self, obj):
        data = ProfileCompletionService.calculate_completion(obj)
        return data["completion_percentage"]

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_verified', 'profile')
        read_only_fields = ('id', 'username', 'email', 'role', 'is_verified')

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)
        
        # Update User fields (first_name, last_name)
        if 'first_name' in validated_data:
            instance.first_name = validated_data['first_name']
        if 'last_name' in validated_data:
            instance.last_name = validated_data['last_name']
        instance.save()

        # Update UserProfile fields
        if profile_data:
            from .models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                if value == "" and attr in ['birth_date', 'latitude', 'longitude']:
                    value = None
                setattr(profile, attr, value)
            profile.save()

        return instance

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            role='USER',
            email_verified=False,
            is_verified=False # False by default, user must confirm via email link
        )
        UserProfile.objects.get_or_create(user=user)
        return user


