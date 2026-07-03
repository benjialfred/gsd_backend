from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import Course, Module, Lesson, CourseEnrollment, LessonProgress
from .serializers import CourseSerializer, ModuleSerializer, LessonSerializer, CourseEnrollmentSerializer, LessonProgressSerializer

class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def enroll(self, request, pk=None):
        course = self.get_object()
        enrollment, created = CourseEnrollment.objects.get_or_create(user=request.user, course=course)
        
        if created:
            return Response({'status': 'enrolled', 'message': 'Inscription réussie.'}, status=status.HTTP_201_CREATED)
        else:
            return Response({'status': 'already_enrolled', 'message': 'Vous êtes déjà inscrit à ce cours.'}, status=status.HTTP_200_OK)

class ModuleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer

class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def complete(self, request, pk=None):
        lesson = self.get_object()
        # Find the enrollment for the course this lesson belongs to
        course = lesson.module.course
        try:
            enrollment = CourseEnrollment.objects.get(user=request.user, course=course)
            progress, created = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
            if not progress.is_completed:
                progress.is_completed = True
                progress.completed_at = timezone.now()
                progress.save()
            return Response({'status': 'completed', 'message': 'Leçon terminée.'}, status=status.HTTP_200_OK)
        except CourseEnrollment.DoesNotExist:
            return Response({'error': 'Vous n\'êtes pas inscrit à ce cours.'}, status=status.HTTP_403_FORBIDDEN)

class EnrollmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CourseEnrollment.objects.filter(user=self.request.user)
