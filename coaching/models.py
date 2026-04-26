from django.db import models
from django.conf import settings

class CoachProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coach_profile')
    specialties = models.TextField()
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, help_text="Taux horaire en FCFA")
    availability_description = models.TextField(blank=True)

    def __str__(self):
        return f"Coach: {self.user.username}"

class Appointment(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'En attente'),
        ('CONFIRMED', 'Confirmé'),
        ('COMPLETED', 'Terminé'),
        ('CANCELLED', 'Annulé'),
    )
    coach = models.ForeignKey(CoachProfile, on_delete=models.CASCADE, related_name='appointments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='booked_appointments')
    appointment_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"RDV: {self.user.username} avec {self.coach.user.username} - {self.appointment_date}"
