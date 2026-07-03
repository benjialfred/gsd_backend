from django.db import models
from django.conf import settings

class NotificationType(models.TextChoices):
    NEW_MATCH = 'NEW_MATCH', 'New Match'
    NEW_MESSAGE = 'NEW_MESSAGE', 'New Message'
    KYC_APPROVED = 'KYC_APPROVED', 'KYC Approved'
    KYC_REJECTED = 'KYC_REJECTED', 'KYC Rejected'
    ACADEMY = 'ACADEMY', 'Academy'
    COACHING = 'COACHING', 'Coaching'
    EVENT = 'EVENT', 'Event'
    SYSTEM = 'SYSTEM', 'System'

class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    related_entity_id = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type}] {self.title} - {self.recipient.username}"

class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    push_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"
