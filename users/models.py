from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Administrateur'),
        ('USER', 'Utilisateur'),
        ('COACH', 'Coach'),
        ('FORMATEUR', 'Formateur'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='USER')
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    denomination = models.CharField(max_length=100, blank=True)
    marital_status = models.CharField(max_length=50, blank=True)
    bio = models.TextField(blank=True)
    objectives = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    def __str__(self):
        return f"Profil de {self.user.username}"
