from rest_framework import serializers
from .models import Course, Module, Lesson, CourseEnrollment, LessonProgress

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = '__all__'

class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    class Meta:
        model = Module
        fields = '__all__'

class CourseSerializer(serializers.ModelSerializer):
    modules = ModuleSerializer(many=True, read_only=True)
    class Meta:
        model = Course
        fields = '__all__'

class LessonProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonProgress
        fields = '__all__'

class CourseEnrollmentSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    lesson_progress = LessonProgressSerializer(many=True, read_only=True)
    
    class Meta:
        model = CourseEnrollment
        fields = '__all__'
