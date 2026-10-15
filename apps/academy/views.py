from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db.models import Count, Q
from .models import Course, Module, Lesson, CourseEnrollment, LessonProgress, DigitalResource
from .serializers import (
    CourseSerializer, ModuleSerializer, LessonSerializer, 
    CourseEnrollmentSerializer, LessonProgressSerializer, DigitalResourceSerializer
)

class IsFormateurOrReadOnly(permissions.BasePermission):
    """
    Lecture autorisée à tous (authentifiés),
    Écriture (création, modification, suppression) réservée aux rôles FORMATEUR et ADMIN.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and (request.user.role in ['FORMATEUR', 'ADMIN'] or request.user.is_staff)


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsFormateurOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        user = self.request.user
        if user and user.is_authenticated:
            # Pré-charger tous les enrollments de l'utilisateur en 1 seule requête
            enrollments = CourseEnrollment.objects.filter(user=user)
            context['user_enrollments'] = {e.course_id: e for e in enrollments}
            # Pré-charger tous les IDs de leçons complétées en 1 seule requête
            completed_lesson_ids = set(
                LessonProgress.objects.filter(
                    enrollment__user=user, 
                    is_completed=True
                ).values_list('lesson_id', flat=True)
            )
            context['completed_lesson_ids'] = completed_lesson_ids
        else:
            context['user_enrollments'] = {}
            context['completed_lesson_ids'] = set()
        return context

    def get_queryset(self):
        user = self.request.user
        queryset = Course.objects.all().select_related('instructor').prefetch_related(
            'modules__lessons'
        ).order_by('-created_at')
        
        # Filtre par catégorie si demandé
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        # Si le formateur demande "mes cours"
        instructor_only = self.request.query_params.get('my_courses')
        if instructor_only and user.is_authenticated:
            queryset = queryset.filter(instructor=user)

        # Si utilisateur non authentifié ou membre classique, ne montrer que les publiés
        if not (user.is_authenticated and (user.role in ['FORMATEUR', 'ADMIN'] or user.is_staff)):
            queryset = queryset.filter(is_published=True)

        return queryset

    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def enroll(self, request, pk=None):
        course = self.get_object()
        enrollment, created = CourseEnrollment.objects.get_or_create(user=request.user, course=course)
        
        if created:
            return Response({'status': 'enrolled', 'message': 'Inscription réussie.'}, status=status.HTTP_201_CREATED)
        else:
            return Response({'status': 'already_enrolled', 'message': 'Vous êtes déjà inscrit à ce cours.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def instructor_stats(self, request):
        """Statistiques d'un formateur pour son dashboard."""
        user = request.user
        if not (user.role in ['FORMATEUR', 'ADMIN'] or user.is_staff):
            return Response({"error": "Réservé aux formateurs."}, status=status.HTTP_403_FORBIDDEN)

        my_courses = Course.objects.filter(instructor=user)
        total_courses = my_courses.count()
        total_students = CourseEnrollment.objects.filter(course__in=my_courses).values('user').distinct().count()
        total_enrollments = CourseEnrollment.objects.filter(course__in=my_courses).count()
        completed_enrollments = CourseEnrollment.objects.filter(course__in=my_courses, is_completed=True).count()
        total_resources = DigitalResource.objects.filter(author=user).count()

        return Response({
            "total_courses": total_courses,
            "total_students": total_students,
            "total_enrollments": total_enrollments,
            "completed_enrollments": completed_enrollments,
            "total_resources": total_resources,
            "completion_rate": int((completed_enrollments / total_enrollments * 100)) if total_enrollments > 0 else 0
        })


class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.all().order_by('order')
    serializer_class = ModuleSerializer
    permission_classes = [IsFormateurOrReadOnly]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        course_id = self.request.query_params.get('course_id')
        if course_id:
            return Module.objects.filter(course_id=course_id).order_by('order')
        return super().get_queryset()


class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.all().order_by('order')
    serializer_class = LessonSerializer
    permission_classes = [IsFormateurOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        module_id = self.request.query_params.get('module_id')
        if module_id:
            return Lesson.objects.filter(module_id=module_id).order_by('order')
        return super().get_queryset()

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def complete(self, request, pk=None):
        lesson = self.get_object()
        course = lesson.module.course
        try:
            enrollment = CourseEnrollment.objects.get(user=request.user, course=course)
            progress, created = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
            if not progress.is_completed:
                progress.is_completed = True
                progress.completed_at = timezone.now()
                progress.save()

            # Vérifier si tout le cours est complété
            total_lessons = course.total_lessons
            completed_count = enrollment.lesson_progress.filter(is_completed=True).count()
            if completed_count >= total_lessons:
                enrollment.is_completed = True
                enrollment.completed_at = timezone.now()
                enrollment.save()

            return Response({
                'status': 'completed',
                'message': 'Leçon terminée avec succès.',
                'course_completed': enrollment.is_completed,
                'progress_percentage': enrollment.progress_percentage
            }, status=status.HTTP_200_OK)
        except CourseEnrollment.DoesNotExist:
            return Response({'error': 'Vous n\'êtes pas inscrit à ce cours.'}, status=status.HTTP_403_FORBIDDEN)


class EnrollmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        return CourseEnrollment.objects.filter(
            user=self.request.user
        ).select_related('course__instructor').prefetch_related(
            'lesson_progress', 'course__modules__lessons'
        ).order_by('-enrolled_at')


class DigitalResourceViewSet(viewsets.ModelViewSet):
    queryset = DigitalResource.objects.all().select_related('author').order_by('-created_at')
    serializer_class = DigitalResourceSerializer
    permission_classes = [IsFormateurOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        queryset = DigitalResource.objects.all().order_by('-created_at')
        resource_type = self.request.query_params.get('type')
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
    def download(self, request, pk=None):
        resource = self.get_object()
        resource.download_count += 1
        resource.save(update_fields=['download_count'])
        return Response({"status": "downloaded", "download_count": resource.download_count})
