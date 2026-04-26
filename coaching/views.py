from rest_framework import viewsets
from .models import CoachProfile, Appointment
from .serializers import CoachProfileSerializer, AppointmentSerializer

class CoachProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CoachProfile.objects.all()
    serializer_class = CoachProfileSerializer

class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
