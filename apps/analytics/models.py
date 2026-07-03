from django.db import models
from django.conf import settings

class UserJourneyEvent(models.Model):
    EVENT_TYPE_CHOICES = (
        ('ONBOARDING_STARTED', 'Onboarding Started'),
        ('ONBOARDING_STEP_COMPLETED', 'Onboarding Step Completed'),
        ('ONBOARDING_ABANDONED', 'Onboarding Abandoned'),
        ('ONBOARDING_RESUMED', 'Onboarding Resumed'),
        ('ONBOARDING_COMPLETED', 'Onboarding Completed'),
        
        ('KYC_STARTED', 'KYC Started'),
        ('KYC_SKIPPED', 'KYC Skipped'),
        ('KYC_ABANDONED', 'KYC Abandoned'),
        ('KYC_SUBMITTED', 'KYC Submitted'),
        ('KYC_APPROVED', 'KYC Approved'),
        ('KYC_REJECTED', 'KYC Rejected'),
        
        ('PROFILE_UPDATED', 'Profile Updated'),
        ('PROFILE_PHOTO_ADDED', 'Profile Photo Added'),
        ('PROFILE_PHOTO_REMOVED', 'Profile Photo Removed'),
        
        # Discovery Events
        ('DISCOVERY_VIEWED', 'Discovery Viewed'),
        ('PROFILE_VIEWED', 'Profile Viewed'),
        ('PROFILE_OPENED', 'Profile Opened'),
        ('PROFILE_LIKED', 'Profile Liked'),
        ('PROFILE_PASSED', 'Profile Passed'),
        ('PROFILE_SUPERLIKED', 'Profile Superliked'),
        ('MATCH_CREATED', 'Match Created'),
        ('MATCH_MODAL_VIEWED', 'Match Modal Viewed'),
        ('COMPATIBILITY_VIEWED', 'Compatibility Viewed'),
        ('MATCH_QUEUE_EMPTY', 'Match Queue Empty'),
        ('DISCOVERY_LIMIT_REACHED', 'Discovery Limit Reached'),
        ('CHAT_STARTED', 'Chat Started'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='journey_events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, db_index=True)
    
    # Détails supplémentaires (ex: quel step a été abandonné, raison du rejet KYC)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_event_type_display()} at {self.created_at}"
