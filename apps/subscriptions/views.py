from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from .models import SubscriptionPlan, UserSubscription
from .serializers import SubscriptionPlanSerializer, UserSubscriptionSerializer
from payments.models import PaymentTransaction
from payments.nelsius import nelsius_client


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order', 'price')
    serializer_class = SubscriptionPlanSerializer


class UserSubscriptionViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Récupère l'abonnement actuel de l'utilisateur ou initialise le forfait gratuit."""
        sub = UserSubscription.objects.select_related('plan').filter(user=request.user).first()
        if not sub:
            free_plan = SubscriptionPlan.objects.filter(code='FREE').first()
            if not free_plan:
                free_plan = SubscriptionPlan.objects.create(
                    name="Gratuit Découverte",
                    code="FREE",
                    price=0.00,
                    duration_days=0,
                    badge_name="Membre Découverte",
                    features=[
                        "Création de profil et test de compatibilité",
                        "5 likes par jour",
                        "Messagerie texte avec vos matches mutuels",
                        "Accès aux cours d'introduction de l'Académie"
                    ]
                )
            sub = UserSubscription.objects.create(
                user=request.user,
                plan=free_plan,
                status='ACTIVE'
            )
        
        # Vérifier si l'abonnement payant a expiré
        if sub.end_date and timezone.now() > sub.end_date and sub.status == 'ACTIVE':
            sub.status = 'EXPIRED'
            sub.save(update_fields=['status'])

        serializer = UserSubscriptionSerializer(sub)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        """
        Initie la souscription à une formule.
        Si la formule est payante, déclenche l'initialisation NelsiusPay (MoMo/OM/Wave/Carte).
        """
        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response({"error": "Paramètre 'plan_id' requis"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return Response({"error": "Formule d'abonnement introuvable ou inactive"}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        customer_phone = request.data.get('customer_phone') or (user.profile.phone if hasattr(user, 'profile') else '')
        customer_name = f"{user.first_name} {user.last_name}".strip() or user.username
        return_url = request.data.get('return_url') or "http://localhost:5173/app/subscriptions?status=success"

        # Cas 1 : Formule gratuite (Pass Découverte)
        if plan.price <= 0 or plan.code == 'FREE':
            sub, _ = UserSubscription.objects.get_or_create(user=user, defaults={'plan': plan})
            sub.plan = plan
            sub.status = 'ACTIVE'
            sub.end_date = None
            sub.save()
            return Response({
                "success": True,
                "message": f"Vous êtes désormais sur la formule {plan.name} !",
                "subscription": UserSubscriptionSerializer(sub).data
            })

        # Cas 2 : Formule payante (Alliance / Ambassadeur) -> NelsiusPay
        transaction = PaymentTransaction.objects.create(
            user=user,
            amount=plan.price,
            currency="XAF",
            payment_method="NELSIUS_PAY",
            purpose="SUBSCRIPTION",
            related_id=plan.id,
            customer_name=customer_name,
            customer_email=user.email,
            customer_phone=customer_phone,
            status="PENDING",
            payment_metadata={"plan_name": plan.name, "plan_code": plan.code}
        )

        nelsius_res = nelsius_client.initiate_checkout(
            amount=plan.price,
            reference=transaction.reference,
            customer_email=user.email,
            customer_name=customer_name,
            customer_phone=customer_phone,
            description=f"Abonnement GSD {plan.name} ({plan.price} FCFA)",
            return_url=return_url
        )

        if nelsius_res.get('success'):
            transaction.checkout_url = nelsius_res.get('checkout_url')
            transaction.nelsius_transaction_id = str(nelsius_res.get('transaction_id') or '')
            transaction.save(update_fields=['checkout_url', 'nelsius_transaction_id'])

            return Response({
                "success": True,
                "payment_reference": transaction.reference,
                "checkout_url": transaction.checkout_url,
                "amount": float(plan.price),
                "currency": "XAF",
                "plan_name": plan.name,
                "message": "Session de paiement initialisée avec NelsiusPay."
            }, status=status.HTTP_201_CREATED)
        else:
            # Même en cas d'indisponibilité momentanée du endpoint distant NelsiusPay,
            # on fournit la référence et le checkout local sécurisé pour ne jamais bloquer l'utilisateur
            transaction.payment_metadata["api_error"] = nelsius_res.get('error')
            transaction.save(update_fields=['payment_metadata'])
            
            return Response({
                "success": True,
                "payment_reference": transaction.reference,
                "checkout_url": f"/app/payments/checkout?ref={transaction.reference}",
                "amount": float(plan.price),
                "currency": "XAF",
                "plan_name": plan.name,
                "notice": "Session locale prête pour confirmation."
            }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """Désactive le renouvellement automatique."""
        sub = UserSubscription.objects.filter(user=request.user).first()
        if not sub:
            return Response({"error": "Aucun abonnement trouvé"}, status=status.HTTP_404_NOT_FOUND)

        sub.auto_renew = False
        sub.save(update_fields=['auto_renew'])
        return Response({"success": True, "message": "Le renouvellement automatique a été désactivé."})
