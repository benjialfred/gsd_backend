from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, Sum, F
from django.db import transaction

from .models import Event, TicketTier, EventRegistration
from .serializers import EventSerializer, TicketTierSerializer, EventRegistrationSerializer


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = EventSerializer

    def get_queryset(self):
        queryset = Event.objects.filter(is_published=True).prefetch_related('ticket_tiers')
        
        event_type = self.request.query_params.get('type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__iexact=city)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(location_name__icontains=search)
            )

        featured = self.request.query_params.get('featured')
        if featured == 'true':
            queryset = queryset.filter(is_featured=True)

        return queryset

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def register(self, request, pk=None):
        event = self.get_object()
        tier_id = request.data.get('ticket_tier_id')
        guest_name = request.data.get('guest_name') or f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
        guest_email = request.data.get('guest_email') or request.user.email
        guest_phone = request.data.get('guest_phone', '')
        notes = request.data.get('notes', '')

        if not tier_id:
            return Response({"error": "Paramètre 'ticket_tier_id' requis"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Verrouiller le ticket_tier pour éviter les surréservations concurrentes
                tier = TicketTier.objects.select_for_update().get(id=tier_id, event=event, is_active=True)
                
                if tier.available_quantity <= 0:
                    return Response({"error": "Désolé, toutes les places pour cette catégorie de billet sont épuisées."}, status=status.HTTP_400_BAD_REQUEST)

                # Décrémenter les places disponibles
                tier.available_quantity = F('available_quantity') - 1
                tier.save(update_fields=['available_quantity'])
                tier.refresh_from_db()

                # Créer le billet / inscription
                registration = EventRegistration.objects.create(
                    event=event,
                    ticket_tier=tier,
                    user=request.user,
                    guest_name=guest_name,
                    guest_email=guest_email,
                    guest_phone=guest_phone,
                    notes=notes,
                    status='CONFIRMED'
                )

            serializer = EventRegistrationSerializer(registration)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except TicketTier.DoesNotExist:
            return Response({"error": "Type de billet invalide ou inactif"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Erreur lors de la réservation: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_tickets(self, request):
        registrations = EventRegistration.objects.filter(
            user=request.user
        ).select_related('event', 'ticket_tier').order_by('-created_at')
        serializer = EventRegistrationSerializer(registrations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def check_in(self, request):
        """
        Point d'émargement / scan de QR code à l'entrée du gala ou de l'événement.
        Réservé aux membres autorisés (Staff, Admin, ou Organisateur).
        """
        qr_hash = request.data.get('qr_code_hash')
        if not qr_hash:
            return Response({"error": "Code QR manquant"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            reg = EventRegistration.objects.select_related('event', 'ticket_tier', 'user').get(qr_code_hash=qr_hash)
        except EventRegistration.DoesNotExist:
            return Response({
                "valid": False,
                "error": "Billet invalide ou introuvable dans le registre officiel GSD."
            }, status=status.HTTP_404_NOT_FOUND)

        if reg.status != 'CONFIRMED':
            return Response({
                "valid": False,
                "error": f"Billet non recevable (Statut: {reg.get_status_display()})."
            }, status=status.HTTP_400_BAD_REQUEST)

        if reg.is_checked_in:
            return Response({
                "valid": False,
                "already_scanned": True,
                "error": f"Billet DÉJÀ ÉMARGÉ le {reg.checked_in_at.strftime('%d/%m/%Y à %H:%M')} !",
                "guest_name": reg.guest_name,
                "ticket_name": reg.ticket_tier.name,
                "event_title": reg.event.title
            }, status=status.HTTP_400_BAD_REQUEST)

        # Valider l'entrée
        reg.is_checked_in = True
        reg.checked_in_at = timezone.now()
        reg.checked_in_by = request.user
        reg.save(update_fields=['is_checked_in', 'checked_in_at', 'checked_in_by'])

        return Response({
            "valid": True,
            "message": f"Accès autorisé pour {reg.guest_name} !",
            "guest_name": reg.guest_name,
            "ticket_name": reg.ticket_tier.name,
            "event_title": reg.event.title,
            "checked_in_at": reg.checked_in_at
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def stats(self, request, pk=None):
        event = self.get_object()
        registrations = event.registrations.filter(status='CONFIRMED')
        total_attendees = registrations.count()
        checked_in_count = registrations.filter(is_checked_in=True).count()
        
        revenue = registrations.aggregate(
            total=Sum('ticket_tier__price')
        )['total'] or 0.00

        return Response({
            "event_id": event.id,
            "event_title": event.title,
            "capacity": event.capacity,
            "total_registered": total_attendees,
            "checked_in_count": checked_in_count,
            "attendance_rate": f"{(checked_in_count / total_attendees * 100):.1f}%" if total_attendees > 0 else "0%",
            "total_revenue_fcfa": float(revenue)
        })
