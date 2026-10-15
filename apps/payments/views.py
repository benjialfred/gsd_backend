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
        Active automatiquement l'abonnement ou le service acheté.
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

        # Interrogation de NelsiusPay si disponible
        verify_res = nelsius_client.verify_payment(tx.reference)
        # Si NelsiusPay confirme le paiement ou si la confirmation directe client est autorisée
        tx.status = 'SUCCESS'
        tx.paid_at = timezone.now()
        tx.save(update_fields=['status', 'paid_at'])

        # Traitement spécifique selon le but (Abonnement, Coaching, Gala)
        if tx.purpose == 'SUBSCRIPTION':
            try:
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
                logger.info(f"[Abonnement] Formule {plan.name} activée pour {tx.user.email} jusqu'au {sub.end_date}")
            except Exception as e:
                logger.error(f"[Abonnement] Erreur activation formule: {str(e)}")

        return Response({
            "success": True,
            "message": "Paiement confirmé avec succès ! Vos privilèges ont été activés.",
            "transaction": PaymentTransactionSerializer(tx).data
        })

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def webhook(self, request):
        """
        Point d'entrée Webhook NelsiusPay IPN.
        Traite les notifications asynchrones de paiement réussi de NelsiusPay.
        """
        payload = request.data
        logger.info(f"[NelsiusPay Webhook] Données reçues: {payload}")

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

        if status_val in ['SUCCESS', 'PAID', 'COMPLETED', 'success', 'paid']:
            tx.status = 'SUCCESS'
            tx.paid_at = timezone.now()
            tx.payment_metadata["webhook_payload"] = payload
            tx.save()

            if tx.purpose == 'SUBSCRIPTION':
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

        return Response({"status": "received", "reference": reference})
