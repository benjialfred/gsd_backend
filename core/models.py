from django.db import models
from django.conf import settings

class Resource(models.Model):
    RESOURCE_TYPES = (
        ('EBOOK', 'E-Book'),
        ('PODCAST', 'Podcast'),
        ('GUIDE', 'Guide Pratique'),
    )
    title = models.CharField(max_length=200)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    description = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role__in': ['FORMATEUR', 'COACH', 'ADMIN']})
    file_url = models.URLField(blank=True, null=True, help_text="Lien vers S3 ou Cloudinary")
    audio_url = models.URLField(blank=True, null=True, help_text="Lien streaming podcast")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Prix en FCFA, 0 si gratuit")
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_resource_type_display()} - {self.title}"

class Transaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_successful = models.BooleanField(default=False)

    def __str__(self):
        return f"Transaction {self.reference} - {self.amount} FCFA"
