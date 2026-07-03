from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

# ---------------------------------------------------------
# Tables de référence administrables
# ---------------------------------------------------------

class Interest(models.Model):
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Language(models.Model):
    code = models.CharField(max_length=10, unique=True) # e.g. 'fr', 'en'
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Sport(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name

class Hobby(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

# ---------------------------------------------------------
# Tables de liaison avec UserProfile
# ---------------------------------------------------------
# Bien que ManyToManyField puisse créer la table de liaison,
# l'utilisation d'un modèle explicite prépare le terrain pour l'ordre, l'affinité, etc.

class UserInterest(models.Model):
    profile = models.ForeignKey('users.UserProfile', on_delete=models.CASCADE, related_name='user_interests')
    interest = models.ForeignKey(Interest, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('profile', 'interest')

class UserLanguage(models.Model):
    profile = models.ForeignKey('users.UserProfile', on_delete=models.CASCADE, related_name='user_languages')
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    # Pourrait inclure le niveau de maîtrise: DEBUTANT, INTERMEDIAIRE, COURANT, MATERNELLE
    
    class Meta:
        unique_together = ('profile', 'language')

class UserSport(models.Model):
    profile = models.ForeignKey('users.UserProfile', on_delete=models.CASCADE, related_name='user_sports')
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('profile', 'sport')

class UserHobby(models.Model):
    profile = models.ForeignKey('users.UserProfile', on_delete=models.CASCADE, related_name='user_hobbies')
    hobby = models.ForeignKey(Hobby, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('profile', 'hobby')

# ---------------------------------------------------------
# ProfileMedia
# ---------------------------------------------------------

class ProfileMedia(models.Model):
    MEDIA_TYPE_CHOICES = (
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
    )
    MODERATION_STATUS_CHOICES = (
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    profile = models.ForeignKey('users.UserProfile', on_delete=models.CASCADE, related_name='media')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='IMAGE')
    file = models.FileField(upload_to='profile_media/')
    is_primary = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    
    # Modération et Vérification
    is_verified_media = models.BooleanField(default=False)
    moderation_status = models.CharField(max_length=20, choices=MODERATION_STATUS_CHOICES, default='PENDING')
    moderated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='moderated_media')
    moderated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', '-created_at']

    def __str__(self):
        return f"{self.media_type} for {self.profile.user.username} (Primary: {self.is_primary})"

# ---------------------------------------------------------
# KYC (Know Your Customer / Profil Certifié)
# ---------------------------------------------------------

class KYCSubmission(models.Model):
    STATUS_CHOICES = (
        ('NOT_SUBMITTED', 'Not Submitted'),
        ('PENDING_REVIEW', 'Pending Review'),
        ('MORE_INFORMATION_REQUIRED', 'More Information Required'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    profile = models.OneToOneField('users.UserProfile', on_delete=models.CASCADE, related_name='kyc_submission')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='NOT_SUBMITTED', db_index=True)
    
    # Documents soumis
    id_document_front = models.FileField(upload_to='kyc_docs/', null=True, blank=True)
    id_document_back = models.FileField(upload_to='kyc_docs/', null=True, blank=True)
    selfie_video = models.FileField(upload_to='kyc_videos/', null=True, blank=True)
    
    # IA / Score de fraude
    verification_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) # e.g. 98.50
    fraud_flag = models.BooleanField(default=False)
    
    submitted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"KYC pour {self.profile.user.username} - {self.get_status_display()}"


class KYCAuditLog(models.Model):
    ACTION_CHOICES = (
        ('SUBMITTED', 'Submitted'),
        ('REVIEW_STARTED', 'Review Started'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('MORE_INFO_REQUESTED', 'More Info Requested'),
    )

    submission = models.ForeignKey(KYCSubmission, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    admin_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} on {self.submission.profile.user.username} at {self.created_at}"
