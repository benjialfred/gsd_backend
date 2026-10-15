from django.db import models
from django.conf import settings

class CoachProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coach_profile')
    title = models.CharField(max_length=150, default="Conseiller Conjugal & Accompagnateur Pastoral")
    bio = models.TextField(blank=True, help_text="Parcours, ministère et vision de l'accompagnement matrimonial")
    specialties = models.TextField(help_text="Spécialités séparées par des virgules ou description")
    years_of_experience = models.PositiveIntegerField(default=10)
    denomination = models.CharField(max_length=100, default="Interdénominationnel")
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=25000.00, help_text="Taux horaire en FCFA")
    languages = models.CharField(max_length=150, default="Français, Anglais")
    avatar_url = models.URLField(blank=True, null=True)
    is_verified = models.BooleanField(default=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    reviews_count = models.PositiveIntegerField(default=12)
    meeting_link = models.URLField(blank=True, null=True, help_text="Lien permanent de visioconférence (Google Meet / WebRTC)")
    availability_description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.title} - {self.user.get_full_name() or self.user.username}"


class AvailabilitySlot(models.Model):
    DAY_CHOICES = (
        (0, 'Lundi'),
        (1, 'Mardi'),
        (2, 'Mercredi'),
        (3, 'Jeudi'),
        (4, 'Vendredi'),
        (5, 'Samedi'),
        (6, 'Dimanche'),
    )
    coach = models.ForeignKey(CoachProfile, on_delete=models.CASCADE, related_name='availability_slots')
    day_of_week = models.IntegerField(choices=DAY_CHOICES, default=0)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.coach.user.username} - {self.get_day_of_week_display()}: {self.start_time} à {self.end_time}"


class Appointment(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'En attente'),
        ('CONFIRMED', 'Confirmé'),
        ('COMPLETED', 'Terminé'),
        ('CANCELLED', 'Annulé'),
    )
    SESSION_TYPES = (
        ('PRE_MARITAL', 'Préparation au Mariage & Alliance'),
        ('COUPLE_CRISIS', 'Résolution de Crise & Pardon'),
        ('SINGLENESS_VISION', 'Orientation Célibat & Discernement'),
        ('SPIRITUAL_DELIVERANCE', 'Sanctification & Délivrance'),
    )
    coach = models.ForeignKey(CoachProfile, on_delete=models.CASCADE, related_name='appointments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='booked_appointments')
    appointment_date = models.DateTimeField()
    duration_minutes = models.IntegerField(default=60)
    session_type = models.CharField(max_length=50, choices=SESSION_TYPES, default='PRE_MARITAL')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    meeting_link = models.URLField(blank=True, null=True)
    user_notes = models.TextField(blank=True, help_text="Sujet de prière ou motif de consultation")
    pastoral_notes = models.TextField(blank=True, help_text="Notes confidentielles du pasteur/coach")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ['-appointment_date']

    def __str__(self):
        return f"RDV: {self.user.username} avec {self.coach.user.username} - {self.appointment_date} ({self.get_status_display()})"
