import uuid
from django.db import models
from django.utils.text import slugify
from users.models import User

EVENT_TYPE_CHOICES = (
    ('GALA', 'Dîner de Gala & Célébration'),
    ('CONFERENCE', 'Conférence & Sommet'),
    ('RETREAT', 'Retraite Spirituelle & Discernement'),
    ('WORKSHOP', 'Atelier & Rencontre d\'Échange'),
)

REGISTRATION_STATUS_CHOICES = (
    ('CONFIRMED', 'Confirmé'),
    ('PENDING', 'En attente'),
    ('CANCELLED', 'Annulé'),
    ('REFUNDED', 'Remboursé'),
)


class Event(models.Model):
    title = models.CharField(max_length=255, verbose_name="Titre de l'événement")
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='GALA')
    description = models.TextField(verbose_name="Description détaillée")
    theme_verse = models.CharField(max_length=255, blank=True, null=True, verbose_name="Verset biblique thème")
    dress_code = models.CharField(max_length=200, blank=True, null=True, verbose_name="Dress Code")
    
    banner_image = models.URLField(max_length=500, blank=True, null=True, verbose_name="Bannière d'illustration")
    location_name = models.CharField(max_length=255, verbose_name="Lieu de l'événement")
    city = models.CharField(max_length=100, default="Douala", verbose_name="Ville")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Adresse")
    
    is_online = models.BooleanField(default=False, verbose_name="Accessible en ligne")
    online_meeting_link = models.URLField(max_length=500, blank=True, null=True, verbose_name="Lien webinaire/retransmission")
    
    start_date = models.DateTimeField(verbose_name="Date & Heure de début")
    end_date = models.DateTimeField(verbose_name="Date & Heure de fin")
    
    capacity = models.PositiveIntegerField(default=150, verbose_name="Capacité maximale")
    is_published = models.BooleanField(default=True, verbose_name="Publié")
    is_featured = models.BooleanField(default=False, verbose_name="Mis en avant (Sommet/Gala)")
    
    organizer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='organized_events')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_date']
        verbose_name = "Événement & Gala"
        verbose_name_plural = "Événements & Galas"

    def __str__(self):
        return f"{self.title} ({self.get_event_type_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or "evenement"
            unique_slug = base_slug
            counter = 1
            while Event.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)


class TicketTier(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_tiers')
    name = models.CharField(max_length=100, verbose_name="Intitulé du billet (ex: Pass VIP)")
    description = models.TextField(blank=True, null=True, verbose_name="Prestations incluses")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Tarif en FCFA")
    capacity = models.PositiveIntegerField(default=50, verbose_name="Nombre total de places")
    available_quantity = models.PositiveIntegerField(default=50, verbose_name="Places disponibles")
    is_active = models.BooleanField(default=True)
    sales_end_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['price']
        verbose_name = "Type de Billet"
        verbose_name_plural = "Types de Billets"

    def __str__(self):
        return f"{self.event.title} - {self.name} ({self.price} FCFA)"


class EventRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    ticket_tier = models.ForeignKey(TicketTier, on_delete=models.CASCADE, related_name='registrations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_registrations')
    
    guest_name = models.CharField(max_length=150, verbose_name="Nom complet sur le billet")
    guest_email = models.EmailField(verbose_name="Email du participant")
    guest_phone = models.CharField(max_length=30, blank=True, null=True, verbose_name="Téléphone / WhatsApp")
    
    qr_code_hash = models.CharField(max_length=64, unique=True, blank=True, verbose_name="Identifiant unique QR Code")
    status = models.CharField(max_length=20, choices=REGISTRATION_STATUS_CHOICES, default='CONFIRMED')
    
    is_checked_in = models.BooleanField(default=False, verbose_name="Émargé à l'entrée")
    checked_in_at = models.DateTimeField(null=True, blank=True, verbose_name="Horodatage d'émargement")
    checked_in_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='scanned_registrations')
    
    notes = models.TextField(blank=True, null=True, verbose_name="Notes particulières")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Inscription / Billet"
        verbose_name_plural = "Inscriptions / Billets"

    def __str__(self):
        return f"Pass #{self.id} - {self.guest_name} ({self.event.title})"

    def save(self, *args, **kwargs):
        if not self.qr_code_hash:
            # Générer un jeton unique lisible et scannable
            clean_uuid = uuid.uuid4().hex[:12].upper()
            self.qr_code_hash = f"GSD-EVT-{self.event_id}-{clean_uuid}"
        super().save(*args, **kwargs)
