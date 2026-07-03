from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CoachProfileViewSet, AppointmentViewSet

router = DefaultRouter()
router.register('profiles', CoachProfileViewSet)
router.register('appointments', AppointmentViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
