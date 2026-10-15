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

    # Code PIN pour reconnexion rapide
    pin_hash = models.CharField(max_length=128, blank=True, null=True, verbose_name="Hash du Code PIN")
    pin_failed_attempts = models.PositiveIntegerField(default=0, verbose_name="Tentatives PIN échouées")
    pin_locked_until = models.DateTimeField(blank=True, null=True, verbose_name="PIN verrouillé jusqu'à")

    # Récupération de mot de passe (Code OTP)
    reset_otp_code = models.CharField(max_length=10, blank=True, null=True, verbose_name="Code OTP de récupération")
    reset_otp_expires_at = models.DateTimeField(blank=True, null=True, verbose_name="Expiration du code OTP")

    @property
    def has_pin(self):
        return bool(self.pin_hash)

    def set_pin(self, raw_pin):
        from django.contrib.auth.hashers import make_password
        self.pin_hash = make_password(str(raw_pin).strip())
        self.pin_failed_attempts = 0
        self.pin_locked_until = None
        self.save(update_fields=['pin_hash', 'pin_failed_attempts', 'pin_locked_until'])

    def check_pin(self, raw_pin):
        from django.contrib.auth.hashers import check_password
        from django.utils import timezone
        from datetime import timedelta

        if not self.pin_hash:
            return False

        if self.pin_locked_until and timezone.now() < self.pin_locked_until:
            return False

        is_correct = check_password(str(raw_pin).strip(), self.pin_hash)
        if is_correct:
            if self.pin_failed_attempts > 0 or self.pin_locked_until is not None:
                self.pin_failed_attempts = 0
                self.pin_locked_until = None
                self.save(update_fields=['pin_failed_attempts', 'pin_locked_until'])
            return True
        else:
            self.pin_failed_attempts += 1
            if self.pin_failed_attempts >= 5:
                self.pin_locked_until = timezone.now() + timedelta(minutes=15)
            self.save(update_fields=['pin_failed_attempts', 'pin_locked_until'])
            return False

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
    city = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_visibility = models.CharField(max_length=20, choices=LOCATION_VISIBILITY_CHOICES, default='CITY_ONLY')
    
    # Préférences de recherche (Onboarding Étape 6)
    pref_age_min = models.IntegerField(default=21)
    pref_age_max = models.IntegerField(default=50)
    pref_distance = models.IntegerField(default=100) # En km
    
    # Onboarding & Statut
    onboarding_completed = models.BooleanField(default=False, db_index=True)
    onboarding_step = models.IntegerField(default=1)
    onboarding_started_at = models.DateTimeField(null=True, blank=True)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Visibilité et confidentialité (Onboarding Étape 9)
    PROFILE_VISIBILITY_CHOICES = (
        ('PUBLIC', 'Public (Tous les membres)'),
        ('MATCHES', 'Mes matchs uniquement'),
        ('HIDDEN', 'Caché'),
    )
    profile_visibility = models.CharField(max_length=20, choices=PROFILE_VISIBILITY_CHOICES, default='PUBLIC')
    
    # KYC (Etat courant dénormalisé pour requêtes rapides)
    kyc_status = models.CharField(max_length=30, choices=KYC_STATUS_CHOICES, default='NOT_SUBMITTED', db_index=True)

    @property
    def age(self):
        if self.birth_date:
            from datetime import date
            today = date.today()
            return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        return None

    def __str__(self):
        return f"Profil de {self.user.username} (KYC: {self.get_kyc_status_display()})"


from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.utils import timezone

@receiver(pre_save, sender=UserProfile)
def send_welcome_email_on_onboarding_completion(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            if not old_instance.onboarding_completed and instance.onboarding_completed:
                if not instance.onboarding_completed_at:
                    instance.onboarding_completed_at = timezone.now()
                
                subject = "Bienvenue au Grand Salon Divin"
                html_message = f"""
                <div style="font-family: 'Times New Roman', serif; color: #1A3A5C; text-align: center; padding: 40px; background-color: #FDFBF7;">
                    <h1 style="font-size: 24px; color: #C9A84C; margin-bottom: 20px; font-weight: normal; letter-spacing: 2px;">
                        LE GRAND SALON DIVIN
                    </h1>
                    <h2 style="font-size: 20px; font-weight: normal; margin-bottom: 30px;">
                        Bienvenue, {instance.user.first_name}
                    </h2>
                    <p style="font-family: Arial, sans-serif; font-size: 14px; color: #4A4A4A; line-height: 1.6; max-width: 600px; margin: 0 auto 30px;">
                        Nous sommes ravis de vous compter parmi nos membres. 
                        Votre profil est maintenant complet. Vous pouvez dès à présent découvrir notre communauté, 
                        accéder à nos événements exclusifs et rencontrer des personnes qui partagent vos valeurs et votre vision.
                    </p>
                    <a href="http://localhost:5173/app" style="display: inline-block; background-color: #1A3A5C; color: #ffffff; padding: 16px 32px; text-decoration: none; font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; letter-spacing: 2px; text-transform: uppercase;">
                        Accéder au Salon
                    </a>
                </div>
                """
                send_mail(
                    subject,
                    "Bienvenue au Grand Salon Divin ! Votre profil est complet. Connectez-vous pour découvrir notre communauté.",
                    'no-reply@gsd.com',
                    [instance.user.email],
                    fail_silently=True,
                    html_message=html_message
                )
        except sender.DoesNotExist:
            pass

