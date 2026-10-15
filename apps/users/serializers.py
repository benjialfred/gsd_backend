from rest_framework import serializers
from .models import User, UserProfile

from profiles.services import ProfileCompletionService

class UserProfileSerializer(serializers.ModelSerializer):
    completion_percentage = serializers.SerializerMethodField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, write_only=True, required=False)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, write_only=True, required=False)
    kyc_status = serializers.CharField(read_only=True)
    
    languages = serializers.SerializerMethodField()
    interests = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    certifications = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'gender', 'birth_date', 'profession', 'education_level', 
            'denomination', 'church_attendance', 'spiritual_commitment',
            'marriage_objectives', 'marriage_values', 'marriage_expectations',
            'marital_status', 'bio', 'objectives', 'avatar',
            'country_code', 'city', 'latitude', 'longitude', 'location_visibility',
            'pref_age_min', 'pref_age_max', 'pref_distance', 'profile_visibility',
            'onboarding_completed', 'onboarding_step', 'onboarding_started_at', 'onboarding_completed_at', 'updated_at',
            'kyc_status', 'completion_percentage',
            'languages', 'interests', 'certifications'
        ]

    def to_internal_value(self, data):
        # Preserve languages and interests which would normally be stripped by SerializerMethodField
        internal_value = super().to_internal_value(data)
        if 'languages' in data:
            internal_value['languages'] = data['languages']
        if 'interests' in data:
            internal_value['interests'] = data['interests']
        return internal_value

    def get_avatar(self, obj):
        url = None
        if obj.avatar:
            try:
                url = obj.avatar.url
            except Exception:
                pass
        if not url:
            primary_media = obj.media.filter(is_primary=True).first() or obj.media.first()
            if primary_media and primary_media.file:
                try:
                    url = primary_media.file.url
                except Exception:
                    pass
        if not url:
            return None
        request = self.context.get('request')
        if request and not url.startswith(('http://', 'https://')):
            return request.build_absolute_uri(url)
        return url

    def get_completion_percentage(self, obj):
        data = ProfileCompletionService.calculate_completion(obj)
        return data["completion_percentage"]
        
    def get_languages(self, obj):
        if hasattr(obj, '_prefetched_objects_cache') and 'user_languages' in obj._prefetched_objects_cache:
            return [l.language_id for l in obj.user_languages.all()]
        return list(obj.user_languages.values_list('language_id', flat=True))
        
    def get_interests(self, obj):
        if hasattr(obj, '_prefetched_objects_cache') and 'user_interests' in obj._prefetched_objects_cache:
            return [i.interest_id for i in obj.user_interests.all()]
        return list(obj.user_interests.values_list('interest_id', flat=True))

    def get_certifications(self, obj):
        try:
            # Si les inscriptions sont déjà préchargées sur l'utilisateur
            user_obj = getattr(obj, 'user', None)
            if user_obj and hasattr(user_obj, '_prefetched_objects_cache') and 'enrollments' in user_obj._prefetched_objects_cache:
                enrollments = [e for e in user_obj.enrollments.all() if e.is_completed]
            else:
                from academy.models import CourseEnrollment
                enrollments = CourseEnrollment.objects.filter(
                    user=obj.user,
                    is_completed=True
                ).select_related('course')
            return [
                {
                    "course_id": enr.course.id,
                    "course_title": enr.course.title,
                    "category": enr.course.category,
                    "category_display": enr.course.get_category_display(),
                    "completed_at": enr.completed_at.isoformat() if enr.completed_at else None,
                    "badge_name": "Certifié Alliance GSD",
                    "badge_level": "Excellence Matrimoniale" if enr.course.category == 'MARRIAGE_PREP' else "Fondation Spirituelle"
                }
                for enr in enrollments
            ]
        except Exception:
            return []

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer()
    has_pin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_verified', 'has_pin', 'profile')
        read_only_fields = ('id', 'username', 'email', 'role', 'is_verified', 'has_pin')

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
            from profiles.models import UserLanguage, UserInterest
            
            languages = profile_data.pop('languages', None)
            interests = profile_data.pop('interests', None)
            
            profile, created = UserProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                if value == "" and attr in ['birth_date', 'latitude', 'longitude']:
                    value = None
                setattr(profile, attr, value)
            profile.save()
            
            if languages is not None:
                UserLanguage.objects.filter(profile=profile).delete()
                # If languages is passed as string like "1,2", split it
                if isinstance(languages, str):
                    languages = [int(x.strip()) for x in languages.split(',') if x.strip().isdigit()]
                for lang_id in languages:
                    UserLanguage.objects.create(profile=profile, language_id=lang_id)
                    
            if interests is not None:
                UserInterest.objects.filter(profile=profile).delete()
                if isinstance(interests, str):
                    interests = [int(x.strip()) for x in interests.split(',') if x.strip().isdigit()]
                for int_id in interests:
                    UserInterest.objects.create(profile=profile, interest_id=int_id)

        return instance

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            role='USER',
            email_verified=False,
            is_verified=False # False by default, user must confirm via email link
        )
        UserProfile.objects.get_or_create(user=user)
        return user


