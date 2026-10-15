import uuid
from django.db import models
from users.models import User

PAYMENT_PURPOSE_CHOICES = (
    ('SUBSCRIPTION', 'Abonnement Membre'),
    ('COACHING', 'Séance Pastorale & Coaching'),
    ('EVENT_TICKET', 'Billet Gala & Événement'),
    ('MARKETPLACE', 'Achat Boutique'),
)

PAYMENT_STATUS_CHOICES = (
    ('PENDING', 'En attente'),
    ('SUCCESS', 'Paiement Réussi'),
    ('FAILED', 'Échoué'),
    ('CANCELLED', 'Annulé'),
)


class PaymentTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    reference = models.CharField(max_length=80, unique=True, verbose_name="Référence unique transaction")
    nelsius_transaction_id = models.CharField(max_length=120, blank=True, null=True, verbose_name="ID NelsiusPay")
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Montant en FCFA")
    currency = models.CharField(max_length=10, default='XAF', verbose_name="Devise")
    payment_method = models.CharField(max_length=50, default='NELSIUS_PAY', verbose_name="Passerelle")
    
    purpose = models.CharField(max_length=30, choices=PAYMENT_PURPOSE_CHOICES, default='SUBSCRIPTION')
    related_id = models.PositiveIntegerField(verbose_name="ID de l'objet associé")
    
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    checkout_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Lien de paiement NelsiusPay")
    
    customer_name = models.CharField(max_length=150)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=35, blank=True, null=True)
    
    payment_metadata = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Transaction de Paiement"
        verbose_name_plural = "Transactions de Paiement"

    def __str__(self):
        return f"Transaction {self.reference} - {self.amount} {self.currency} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.reference:
            clean_uuid = uuid.uuid4().hex[:10].upper()
            self.reference = f"GSD-PAY-{clean_uuid}"
        super().save(*args, **kwargs)
