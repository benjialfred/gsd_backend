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
    is_verified = models.BooleanField(default=False) # Legacy field
    email_verified = models.BooleanField(default=False) # Technical confirmation

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class UserProfile(models.Model):
    KYC_STATUS_CHOICES = (
        ('NOT_SUBMITTED', 'Not Submitted'),
        ('PENDING_REVIEW', 'Pending Review'),
        ('MORE_INFORMATION_REQUIRED', 'More Information Required'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    GENDER_CHOICES = (
        ('M', 'Homme'),
        ('F', 'Femme'),
    )

    LOCATION_VISIBILITY_CHOICES = (
        ('EXACT', 'Exact'),
        ('CITY_ONLY', 'City Only'),
        ('HIDDEN', 'Hidden'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Identité
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True, db_index=True)
    birth_date = models.DateField(blank=True, null=True, db_index=True)
    
    # Vie spirituelle & autres existants
    denomination = models.CharField(max_length=100, blank=True, db_index=True)
    church_attendance = models.CharField(max_length=100, blank=True)
    spiritual_commitment = models.TextField(blank=True)
    
    # Profession & Études
    profession = models.CharField(max_length=100, blank=True)
    education_level = models.CharField(max_length=100, blank=True)
    
    # Vision du mariage
    marriage_objectives = models.TextField(blank=True)
    marriage_values = models.TextField(blank=True)
    marriage_expectations = models.TextField(blank=True)
    
    marital_status = models.CharField(max_length=50, blank=True)
    bio = models.TextField(blank=True)
    objectives = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    # Géolocalisation
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_visibility = models.CharField(max_length=20, choices=LOCATION_VISIBILITY_CHOICES, default='CITY_ONLY')
    
    # Onboarding
    onboarding_completed = models.BooleanField(default=False, db_index=True)
    onboarding_step = models.IntegerField(default=0)
    
    # KYC (Etat courant dénormalisé pour requêtes rapides)
    kyc_status = models.CharField(max_length=30, choices=KYC_STATUS_CHOICES, default='NOT_SUBMITTED', db_index=True)

    def __str__(self):
        return f"Profil de {self.user.username} (KYC: {self.get_kyc_status_display()})"

