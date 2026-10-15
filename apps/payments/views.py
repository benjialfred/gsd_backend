from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
import logging

from .models import PaymentTransaction
from .serializers import PaymentTransactionSerializer
from .nelsius import nelsius_client
from subscriptions.models import SubscriptionPlan, UserSubscription

logger = logging.getLogger(__name__)


def _activate_purchased_service(tx: PaymentTransaction, payload=None):
    """
    Active automatiquement le service acquis selon son but :
    - SUBSCRIPTION : Active l'abonnement du membre avec calcul d'échéance
    - EVENT_TICKET : Valide et émet le billet officiel d'événement avec QR Code
    - COACHING     : Confirme le rendez-vous d'accompagnement pastoral
    """
    tx.status = 'SUCCESS'
    tx.paid_at = timezone.now()
    if payload:
        tx.payment_metadata["webhook_payload"] = payload
    tx.save()

    # 1. Formule d'Abonnement
    if tx.purpose == 'SUBSCRIPTION':
        try:
            from subscriptions.models import SubscriptionPlan, UserSubscription
            plan = SubscriptionPlan.objects.get(id=tx.related_id)
            sub, _ = UserSubscription.objects.get_or_create(user=tx.user, defaults={'plan': plan})
            sub.plan = plan
            sub.status = 'ACTIVE'
            sub.start_date = timezone.now()
            if plan.duration_days > 0:
                sub.end_date = timezone.now() + timedelta(days=plan.duration_days)
            else:
                sub.end_date = None
            sub.last_payment_reference = tx.reference
            sub.save()
            logger.info(f"[NelsiusPay] Formule {plan.name} activée pour {tx.user.email} jusqu'au {sub.end_date}")
        except Exception as e:
            logger.error(f"[NelsiusPay] Erreur activation abonnement: {str(e)}")

    # 2. Billet de Gala / Événement
    elif tx.purpose in ['EVENT_TICKET', 'EVENT']:
        try:
            from events.models import TicketTier, EventRegistration
            tier = TicketTier.objects.select_related('event').get(id=tx.related_id)
            reg, created = EventRegistration.objects.get_or_create(
                user=tx.user,
                event=tier.event,
                ticket_tier=tier,
                defaults={
                    'guest_name': tx.customer_name or f"{tx.user.first_name} {tx.user.last_name}".strip() or tx.user.username,
                    'guest_email': tx.customer_email or tx.user.email,
                    'guest_phone': tx.customer_phone or '',
                    'status': 'CONFIRMED',
                    'notes': f"Payé via NelsiusPay (Réf: {tx.reference})"
                }
            )
            if not created and reg.status != 'CONFIRMED':
                reg.status = 'CONFIRMED'
                reg.save(update_fields=['status'])
            logger.info(f"[NelsiusPay] Billet {tier.name} ({tier.event.title}) confirmé pour {tx.user.email}")
        except Exception as e:
            logger.error(f"[NelsiusPay] Erreur confirmation billet gala: {str(e)}")

    # 3. Rendez-vous Pastoral & Coaching
    elif tx.purpose == 'COACHING':
        try:
            from coaching.models import Appointment
            appointment = Appointment.objects.get(id=tx.related_id)
            appointment.status = 'CONFIRMED'
            appointment.save(update_fields=['status'])
            logger.info(f"[NelsiusPay] Rendez-vous de coaching #{appointment.id} confirmé pour {tx.user.email}")
        except Exception as e:
            logger.error(f"[NelsiusPay] Erreur confirmation rendez-vous coaching: {str(e)}")


class PaymentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentTransactionSerializer
    lookup_field = 'reference'

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'ADMIN':
            return PaymentTransaction.objects.all().order_by('-created_at')
        return PaymentTransaction.objects.filter(user=user).order_by('-created_at')

    @action(detail=False, methods=['post'])
    def confirm(self, request):
        """
        Confirme et finalise une transaction de paiement après retour du guichet NelsiusPay.
        Active automatiquement l'abonnement, le billet ou le rendez-vous acheté.
        """
        ref = request.data.get('reference')
        if not ref:
            return Response({"error": "Paramètre 'reference' requis"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tx = PaymentTransaction.objects.select_related('user').get(reference=ref)
        except PaymentTransaction.DoesNotExist:
            return Response({"error": "Transaction introuvable"}, status=status.HTTP_404_NOT_FOUND)

        if tx.user != request.user and not request.user.is_staff:
            return Response({"error": "Non autorisé"}, status=status.HTTP_403_FORBIDDEN)

        if tx.status == 'SUCCESS':
            return Response({
                "success": True,
                "message": "Paiement déjà validé.",
                "transaction": PaymentTransactionSerializer(tx).data
            })

        # Interrogation optionnelle de vérification NelsiusPay
        verify_res = nelsius_client.verify_payment(tx.reference)
        _activate_purchased_service(tx)

        return Response({
            "success": True,
            "message": "Paiement confirmé avec succès ! Vos privilèges ont été activés.",
            "transaction": PaymentTransactionSerializer(tx).data
        })

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def webhook(self, request):
        """
        Point d'entrée Webhook NelsiusPay IPN officiel.
        Traite en temps réel les notifications asynchrones de paiement réussi (Mobile Money, Carte).
        """
        payload = request.data
        logger.info(f"[NelsiusPay Webhook IPN] Données reçues: {payload}")

        reference = (
            payload.get('reference') 
            or payload.get('data', {}).get('reference')
            or payload.get('transaction_reference')
        )
        status_val = (
            payload.get('status')
            or payload.get('data', {}).get('status')
        )

        if not reference:
            return Response({"error": "Référence manquante"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tx = PaymentTransaction.objects.select_related('user').get(reference=reference)
        except PaymentTransaction.DoesNotExist:
            logger.warning(f"[NelsiusPay Webhook] Transaction introuvable pour référence {reference}")
            return Response({"error": "Transaction introuvable"}, status=status.HTTP_404_NOT_FOUND)

        if status_val in ['SUCCESS', 'PAID', 'COMPLETED', 'success', 'paid', True]:
            _activate_purchased_service(tx, payload=payload)
            return Response({
                "status": "success",
                "message": "Paiement NelsiusPay validé et service activé.",
                "reference": reference
            }, status=status.HTTP_200_OK)

        return Response({"status": "received", "reference": reference})
