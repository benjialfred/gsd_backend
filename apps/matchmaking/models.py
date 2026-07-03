from django.db import models
from django.conf import settings

class Match(models.Model):
    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='matches_as_user1')
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='matches_as_user2')
    is_accepted = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    
    # Préparation du Chat Sprint 5
    conversation_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Compatibilité figée au moment du match
    compatibility_score = models.IntegerField(default=0)
    compatibility_breakdown = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user1', 'user2')

    def __str__(self):
        return f"Match: {self.user1.username} & {self.user2.username}"

class SuggestionStatus(models.TextChoices):
    NEW = 'NEW', 'New'
    VIEWED = 'VIEWED', 'Viewed'
    LIKED = 'LIKED', 'Liked'
    PASSED = 'PASSED', 'Passed'
    MATCHED = 'MATCHED', 'Matched'
    EXPIRED = 'EXPIRED', 'Expired'

class MatchCandidate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='candidate_suggestions')
    candidate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='suggested_to')
    compatibility_score = models.JSONField(default=dict) # Stocke le breakdown structuré complet
    generated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=SuggestionStatus.choices, default=SuggestionStatus.NEW)
    feed_version = models.CharField(max_length=20, default='v1', db_index=True)

    class Meta:
        unique_together = ('user', 'candidate')

    def __str__(self):
        return f"Candidate {self.candidate.username} for {self.user.username} ({self.status})"

class SwipeAction(models.Model):
    ACTION_CHOICES = (
        ('LIKE', 'Like'),
        ('PASS', 'Pass'),
        ('SUPER_LIKE', 'Super Like'), # Préparé mais inactif
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='swipes_sent')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='swipes_received')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender.username} {self.action} {self.receiver.username}"

class Message(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Message de {self.sender.username} - {self.timestamp}"

# ---------------------------------------------------------
# Préférences de Matchmaking
# ---------------------------------------------------------

class MatchPreferences(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='match_preferences')
    
    preferred_age_min = models.IntegerField(default=18)
    preferred_age_max = models.IntegerField(default=99)
    preferred_distance = models.IntegerField(default=100, help_text="Distance en km")
    preferred_country = models.CharField(max_length=2, blank=True)
    
    # Relations M2M pour les préférences spécifiques
    preferred_languages = models.ManyToManyField('profiles.Language', blank=True)
    
    # Choix multiples possibles stockés via ArrayField ou JSONField,
    # ou une relation M2M vers un modèle de référence "Denomination".
    # Pour garder simple et scalable, nous utilisons un JSONField pour des listes de strings, 
    # ou mieux, une structure relationnelle. Utilisons JSONField pour le moment pour les dénominations
    # si elles ne sont pas dans une table de référence.
    preferred_denominations = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Préférences de {self.user.username}"


class DealBreakerType(models.Model):
    code = models.CharField(max_length=50, unique=True) # e.g. 'SMOKING', 'ALCOHOL', 'CHILDREN', 'DISTANCE'
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class UserDealBreaker(models.Model):
    preferences = models.ForeignKey(MatchPreferences, on_delete=models.CASCADE, related_name='deal_breakers')
    deal_breaker_type = models.ForeignKey(DealBreakerType, on_delete=models.CASCADE)
    value = models.CharField(max_length=255) # e.g. "NO", "100km", "HIGH"

    class Meta:
        unique_together = ('preferences', 'deal_breaker_type')

    def __str__(self):
        return f"{self.preferences.user.username} - {self.deal_breaker_type.code}: {self.value}"
