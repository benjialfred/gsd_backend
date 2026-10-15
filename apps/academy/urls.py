from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CourseViewSet, ModuleViewSet, LessonViewSet, EnrollmentViewSet, DigitalResourceViewSet

router = DefaultRouter()
router.register('courses', CourseViewSet, basename='courses')
router.register('modules', ModuleViewSet, basename='modules')
router.register('lessons', LessonViewSet, basename='lessons')
router.register('enrollments', EnrollmentViewSet, basename='enrollments')
router.register('resources', DigitalResourceViewSet, basename='resources')

urlpatterns = [
    path('', include(router.urls)),
]
