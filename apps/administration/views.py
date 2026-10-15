from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User, UserProfile
from profiles.models import KYCSubmission, KYCAuditLog
from profiles.serializers import KYCSubmissionSerializer
from payments.models import PaymentTransaction
from events.models import Event, EventRegistration, TicketTier
from coaching.models import CoachProfile, Appointment
from subscriptions.models import UserSubscription
from analytics.models import UserJourneyEvent

from .serializers import (
    AdminUserSerializer,
    AdminTransactionSerializer,
    AdminEventSerializer,
    AdminRegistrationSerializer,
    AdminAuditLogSerializer,
    AdminCoachSerializer
)


class IsAdminUser(permissions.BasePermission):
    """
    Autorise les administrateurs GSD (is_staff=True, role='ADMIN' ou superutilisateur).
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return bool(
            request.user.is_staff or 
            request.user.is_superuser or 
            getattr(request.user, 'role', '') == 'ADMIN'
        )


class AdminMetricsView(APIView):
    """
    Agrégation temps réel et 100% réelle (zéro mock) des données d'exploitation.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        thirty_days_ago = now - timezone.timedelta(days=30)

        # 1. Utilisateurs
        total_users = User.objects.count()
        new_users_30d = User.objects.filter(date_joined__gte=thirty_days_ago).count()
        active_profiles = UserProfile.objects.count()
        completed_onboarding = UserProfile.objects.filter(onboarding_completed=True).count()

        # 2. KYC Compliance
        kyc_pending = KYCSubmission.objects.filter(status='PENDING_REVIEW').count()
        kyc_approved = KYCSubmission.objects.filter(status='APPROVED').count()
        kyc_rejected = KYCSubmission.objects.filter(status='REJECTED').count()
        kyc_more_info = KYCSubmission.objects.filter(status='MORE_INFORMATION_REQUIRED').count()

        # 3. Finances & Transactions NelsiusPay
        successful_tx = PaymentTransaction.objects.filter(status='SUCCESS')
        total_revenue_fcfa = successful_tx.aggregate(total=Sum('amount'))['total'] or 0
        total_transactions = PaymentTransaction.objects.count()
        pending_transactions = PaymentTransaction.objects.filter(status='PENDING').count()
        failed_transactions = PaymentTransaction.objects.filter(status='FAILED').count()

        revenue_subscriptions = successful_tx.filter(purpose='SUBSCRIPTION').aggregate(total=Sum('amount'))['total'] or 0
        revenue_events = successful_tx.filter(purpose='EVENT_TICKET').aggregate(total=Sum('amount'))['total'] or 0
        revenue_coaching = successful_tx.filter(purpose='COACHING').aggregate(total=Sum('amount'))['total'] or 0

        # 4. Événements & Billetterie
        total_events = Event.objects.count()
        published_events = Event.objects.filter(is_published=True).count()
        confirmed_registrations = EventRegistration.objects.filter(status='CONFIRMED').count()
        checked_in_registrations = EventRegistration.objects.filter(is_checked_in=True).count()

        # 5. Coaching Pastoral
        total_coaches = CoachProfile.objects.count()
        total_appointments = Appointment.objects.count()
        confirmed_appointments = Appointment.objects.filter(status='CONFIRMED').count()

        # 6. Abonnements
        active_subscriptions = UserSubscription.objects.filter(status='ACTIVE').count()

        data = {
            "users": {
                "total": total_users,
                "new_30d": new_users_30d,
                "active_profiles": active_profiles,
                "onboarding_completed": completed_onboarding,
            },
            "kyc": {
                "pending": kyc_pending,
                "approved": kyc_approved,
                "rejected": kyc_rejected,
                "more_info": kyc_more_info,
            },
            "finances": {
                "total_revenue_fcfa": float(total_revenue_fcfa),
                "total_transactions": total_transactions,
                "successful_transactions": successful_tx.count(),
                "pending_transactions": pending_transactions,
                "failed_transactions": failed_transactions,
                "breakdown": {
                    "subscriptions_fcfa": float(revenue_subscriptions),
                    "events_fcfa": float(revenue_events),
                    "coaching_fcfa": float(revenue_coaching),
                }
            },
            "events": {
                "total_events": total_events,
                "published_events": published_events,
                "confirmed_registrations": confirmed_registrations,
                "checked_in_registrations": checked_in_registrations,
            },
            "coaching": {
                "total_coaches": total_coaches,
                "total_appointments": total_appointments,
                "confirmed_appointments": confirmed_appointments,
            },
            "subscriptions": {
                "active_members": active_subscriptions
            }
        }
        return Response(data)


class AdminUsersListView(generics.ListAPIView):
    """
    Liste complète des utilisateurs avec recherche et filtres pour la modération.
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        queryset = User.objects.all().select_related('profile').order_by('-date_joined')
        
        # Filtre texte
        q = self.request.query_params.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(username__icontains=q) |
                Q(email__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(profile__city__icontains=q)
            )

        # Filtre rôle
        role = self.request.query_params.get('role', '').strip()
        if role:
            queryset = queryset.filter(role=role)

        # Filtre actif
        is_active = self.request.query_params.get('is_active')
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() in ('true', '1'))

        # Filtre KYC
        kyc = self.request.query_params.get('kyc_status', '').strip()
        if kyc:
            queryset = queryset.filter(profile__kyc_submission__status=kyc)

        return queryset[:100]


class AdminUserDetailView(APIView):
    """
    Détail et mise à jour d'un utilisateur par l'administrateur.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        try:
            user = User.objects.select_related('profile').get(pk=pk)
            serializer = AdminUserSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({"error": "Utilisateur introuvable"}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "Utilisateur introuvable"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        if 'role' in data and data['role'] in dict(User.ROLE_CHOICES):
            user.role = data['role']
        if 'is_active' in data:
            user.is_active = bool(data['is_active'])
        if 'is_staff' in data:
            user.is_staff = bool(data['is_staff'])
        if 'email_verified' in data:
            user.email_verified = bool(data['email_verified'])

        user.save()
        return Response(AdminUserSerializer(user).data)


class AdminTransactionsListView(generics.ListAPIView):
    """
    Audit financier en temps réel des transactions NelsiusPay.
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminTransactionSerializer

    def get_queryset(self):
        queryset = PaymentTransaction.objects.all().order_by('-created_at')

        status_filter = self.request.query_params.get('status', '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        purpose_filter = self.request.query_params.get('purpose', '').strip()
        if purpose_filter:
            queryset = queryset.filter(purpose=purpose_filter)

        q = self.request.query_params.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(reference__icontains=q) |
                Q(customer_name__icontains=q) |
                Q(customer_email__icontains=q) |
                Q(customer_phone__icontains=q)
            )

        return queryset[:100]


class AdminEventsListView(generics.ListCreateAPIView):
    """
    Liste des événements pour administration et création de nouveaux galas.
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminEventSerializer

    def get_queryset(self):
        return Event.objects.all().prefetch_related('ticket_tiers', 'registrations').order_by('-start_date')

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)


class AdminEventDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Modification et publication d'un événement.
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminEventSerializer
    queryset = Event.objects.all()


class AdminRegistrationsListView(generics.ListAPIView):
    """
    Liste des inscrits / billets avec code QR pour émargement.
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminRegistrationSerializer

    def get_queryset(self):
        queryset = EventRegistration.objects.all().select_related('event', 'ticket_tier').order_by('-created_at')
        event_id = self.request.query_params.get('event_id')
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        
        q = self.request.query_params.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(guest_name__icontains=q) |
                Q(guest_email__icontains=q) |
                Q(qr_code_hash__icontains=q)
            )
        return queryset[:100]


class AdminCheckInView(APIView):
    """
    Validation et émargement de billet par QR Code Hash.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        qr_hash = request.data.get('qr_code_hash', '').strip()
        if not qr_hash:
            return Response({"error": "Le hash du QR Code est requis."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            reg = EventRegistration.objects.select_related('event', 'ticket_tier').get(qr_code_hash=qr_hash)
        except EventRegistration.DoesNotExist:
            return Response({"error": "Billet introuvable pour ce QR code."}, status=status.HTTP_404_NOT_FOUND)

        if reg.is_checked_in:
            return Response({
                "status": "already_checked_in",
                "message": f"Ce billet a déjà été émargé le {reg.checked_in_at.strftime('%d/%m/%Y à %H:%M') if reg.checked_in_at else ''}",
                "registration": AdminRegistrationSerializer(reg).data
            }, status=status.HTTP_200_OK)

        reg.is_checked_in = True
        reg.checked_in_at = timezone.now()
        reg.checked_in_by = request.user
        reg.save()

        return Response({
            "status": "success",
            "message": f"Accès Validé pour {reg.guest_name} ({reg.ticket_tier.name})",
            "registration": AdminRegistrationSerializer(reg).data
        })


class AdminCoachesListView(generics.ListAPIView):
    """
    Liste des profils de conseillers et coachs matrimoniaux.
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminCoachSerializer
    queryset = CoachProfile.objects.all().select_related('user').prefetch_related('appointments')


class AdminAuditLogsView(generics.ListAPIView):
    """
    Journal d'audit administratif.
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminAuditLogSerializer
    queryset = KYCAuditLog.objects.all().select_related('admin_user', 'submission__profile__user').order_by('-created_at')[:50]


# --- Vues KYC Existantes préservées ---

class KYCQueueView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = KYCSubmissionSerializer
    
    def get_queryset(self):
        status_filter = self.request.query_params.get('status', 'PENDING_REVIEW')
        return KYCSubmission.objects.filter(status=status_filter).order_by('submitted_at')


class KYCReviewView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            submission = KYCSubmission.objects.get(pk=pk)
        except KYCSubmission.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
            
        action = request.data.get('action') # APPROVED, REJECTED, MORE_INFORMATION_REQUIRED
        reason = request.data.get('reason', '')
        
        if action not in ['APPROVED', 'REJECTED', 'MORE_INFORMATION_REQUIRED']:
            return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)
            
        submission.status = action
        submission.save()
        
        # Log Audit
        KYCAuditLog.objects.create(
            submission=submission,
            action=action,
            admin_user=request.user,
            comments=reason
        )
        
        # Mettre à jour le statut KYC de l'utilisateur
        profile = submission.profile
        profile.kyc_status = action
        profile.save()
        
        # Émettre l'événement
        UserJourneyEvent.objects.create(
            user=profile.user,
            event_type=f'KYC_{action}',
            metadata={'reason': reason}
        )

        return Response({"status": "success", "new_status": action})
