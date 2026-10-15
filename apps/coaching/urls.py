from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CoachProfileViewSet, AvailabilitySlotViewSet, AppointmentViewSet

router = DefaultRouter()
router.register('profiles', CoachProfileViewSet, basename='coach-profile')
router.register('slots', AvailabilitySlotViewSet, basename='availability-slot')
router.register('appointments', AppointmentViewSet, basename='appointment')

urlpatterns = [
    path('', include(router.urls)),
]
