from django.db import models
from django.utils import timezone
from users.models import User

PLAN_CODE_CHOICES = (
    ('FREE', 'Gratuit Découverte'),
    ('ALLIANCE', 'Pass Alliance'),
    ('AMBASSADOR', 'Ambassadeur Royal'),
)

BILLING_CYCLE_CHOICES = (
    ('MONTHLY', 'Mensuel (30 jours)'),
    ('QUARTERLY', 'Trimestriel (90 jours)'),
    ('YEARLY', 'Annuel (365 jours)'),
    ('LIFETIME', 'À Vie'),
)

SUBSCRIPTION_STATUS_CHOICES = (
    ('ACTIVE', 'Actif'),
    ('PENDING', 'En attente de paiement'),
    ('EXPIRED', 'Expiré'),
    ('CANCELLED', 'Résilié'),
)


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nom de la formule")
    code = models.CharField(max_length=30, choices=PLAN_CODE_CHOICES, unique=True, verbose_name="Code unique")
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES, default='MONTHLY')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Prix en FCFA")
    duration_days = models.PositiveIntegerField(default=30, verbose_name="Durée de validité en jours")
    
    badge_name = models.CharField(max_length=60, default="Membre Standard", verbose_name="Badge profil")
    badge_color = models.CharField(max_length=20, default="#1A3A5C")
    description = models.TextField(blank=True, null=True)
    features = models.JSONField(default=list, verbose_name="Liste des avantages inclus")
    
    # Permissions & Quotas
    daily_likes_limit = models.PositiveIntegerField(default=5, verbose_name="Limite de likes quotidiens")
    can_see_likes = models.BooleanField(default=False, verbose_name="Voir les profils qui ont aimé")
    can_call = models.BooleanField(default=False, verbose_name="Appels audio & vidéo sécurisés")
    can_use_audio_notes = models.BooleanField(default=False, verbose_name="Notes vocales illimitées")
    has_academy_access = models.BooleanField(default=False, verbose_name="Accès complet E-Academy")
    discount_percentage = models.PositiveIntegerField(default=0, verbose_name="Remise sur coaching & galas (%)")
    
    is_featured = models.BooleanField(default=False, verbose_name="Mettre en avant (Recommandé)")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'price']
        verbose_name = "Formule d'Abonnement"
        verbose_name_plural = "Formules d'Abonnement"

    def __str__(self):
        return f"{self.name} ({self.price} FCFA / {self.get_billing_cycle_display()})"


class UserSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscribers')
    status = models.CharField(max_length=20, choices=SUBSCRIPTION_STATUS_CHOICES, default='ACTIVE')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Date d'expiration")
    auto_renew = models.BooleanField(default=True)
    last_payment_reference = models.CharField(max_length=120, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Abonnement Utilisateur"
        verbose_name_plural = "Abonnements Utilisateurs"

    def __str__(self):
        return f"Abonnement de {self.user.email} - {self.plan.name} ({self.status})"

    @property
    def is_valid(self):
        if self.status != 'ACTIVE':
            return False
        if self.end_date is None:
            return True # Plan gratuit ou permanent
        return timezone.now() <= self.end_date

    @property
    def days_remaining(self):
        if not self.end_date:
            return 9999
        now = timezone.now()
        if now > self.end_date:
            return 0
        return (self.end_date - now).days
