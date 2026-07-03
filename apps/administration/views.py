from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from profiles.models import KYCSubmission, KYCAuditLog
from profiles.serializers import KYCSubmissionSerializer
from analytics.models import UserJourneyEvent

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)

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
