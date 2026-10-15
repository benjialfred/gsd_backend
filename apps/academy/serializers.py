from rest_framework import serializers
from .models import Course, Module, Lesson, CourseEnrollment, LessonProgress, DigitalResource

class LessonSerializer(serializers.ModelSerializer):
    is_completed = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'module', 'title', 'content', 'lesson_type', 
            'video_url', 'video_file', 'audio_file', 'audio_url', 
            'attachment', 'attachment_url', 'duration_minutes', 
            'order', 'is_completed'
        ]
        extra_kwargs = {
            'video_url': {'required': False, 'allow_null': True, 'allow_blank': True},
            'video_file': {'required': False, 'allow_null': True},
            'audio_file': {'required': False, 'allow_null': True},
            'attachment': {'required': False, 'allow_null': True},
        }

    def get_is_completed(self, obj):
        completed_ids = self.context.get('completed_lesson_ids')
        if completed_ids is not None:
            return obj.id in completed_ids
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return LessonProgress.objects.filter(
                enrollment__user=request.user,
                enrollment__course=obj.module.course,
                lesson=obj,
                is_completed=True
            ).exists()
        return False

    def get_audio_url(self, obj):
        request = self.context.get('request')
        if obj.audio_file:
            return request.build_absolute_uri(obj.audio_file.url) if request else obj.audio_file.url
        return None

    def get_attachment_url(self, obj):
        request = self.context.get('request')
        if obj.attachment:
            return request.build_absolute_uri(obj.attachment.url) if request else obj.attachment.url
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.video_file:
            data['video_url'] = request.build_absolute_uri(instance.video_file.url) if request else instance.video_file.url
        return data


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'course', 'title', 'order', 'lessons']


class CourseSerializer(serializers.ModelSerializer):
    modules = ModuleSerializer(many=True, read_only=True)
    instructor_name = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    total_lessons_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'category', 'level', 
            'instructor', 'instructor_name', 'thumbnail', 'thumbnail_url', 
            'duration_hours', 'is_premium', 'certificate_available', 
            'is_published', 'modules', 'is_enrolled', 'progress_percentage', 
            'total_lessons_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ('instructor', 'created_at', 'updated_at')
        extra_kwargs = {
            'thumbnail': {'required': False, 'allow_null': True},
            'thumbnail_url': {'required': False, 'allow_null': True, 'allow_blank': True},
        }

    def get_instructor_name(self, obj):
        if obj.instructor:
            return f"{obj.instructor.first_name} {obj.instructor.last_name}".strip() or obj.instructor.username
        return "Instructeur GSD"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.thumbnail:
            data['thumbnail_url'] = request.build_absolute_uri(instance.thumbnail.url) if request else instance.thumbnail.url
        elif not data.get('thumbnail_url'):
            data['thumbnail_url'] = "https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=800&q=80"
        return data

    def get_is_enrolled(self, obj):
        enrollments = self.context.get('user_enrollments')
        if enrollments is not None:
            return obj.id in enrollments
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return CourseEnrollment.objects.filter(user=request.user, course=obj).exists()
        return False

    def get_progress_percentage(self, obj):
        enrollments = self.context.get('user_enrollments')
        if enrollments is not None:
            enrollment = enrollments.get(obj.id)
            if enrollment:
                return enrollment.progress_percentage
            return 0
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            enrollment = CourseEnrollment.objects.filter(user=request.user, course=obj).first()
            if enrollment:
                return enrollment.progress_percentage
        return 0

    def get_total_lessons_count(self, obj):
        # Utiliser les modules pré-chargés en mémoire si disponibles
        if hasattr(obj, '_prefetched_objects_cache') and 'modules' in obj._prefetched_objects_cache:
            return sum(len(m.lessons.all()) for m in obj.modules.all())
        return obj.total_lessons


class LessonProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonProgress
        fields = '__all__'


class CourseEnrollmentSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    lesson_progress = LessonProgressSerializer(many=True, read_only=True)
    progress_percentage = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = CourseEnrollment
        fields = ['id', 'user', 'course', 'enrolled_at', 'is_completed', 'completed_at', 'lesson_progress', 'progress_percentage']


class DigitalResourceSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()
    document_url = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = DigitalResource
        fields = [
            'id', 'title', 'description', 'resource_type', 'category',
            'author', 'author_name', 'price', 'is_free', 'image_url', 'image',
            'external_url', 'audio_file', 'audio_url', 'document_file', 
            'document_url', 'duration_minutes', 'download_count', 'created_at'
        ]
        read_only_fields = ('author', 'download_count', 'created_at')

    def get_author_name(self, obj):
        if obj.author:
            return f"{obj.author.first_name} {obj.author.last_name}".strip() or obj.author.username
        return "Équipe Pastorale GSD"

    def get_audio_url(self, obj):
        request = self.context.get('request')
        if obj.audio_file:
            return request.build_absolute_uri(obj.audio_file.url) if request else obj.audio_file.url
        return None

    def get_document_url(self, obj):
        request = self.context.get('request')
        if obj.document_file:
            return request.build_absolute_uri(obj.document_file.url) if request else obj.document_file.url
        return obj.external_url

    def get_image(self, obj):
        return obj.image_url or "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=800&q=80"
