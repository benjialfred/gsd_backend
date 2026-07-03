from rest_framework import viewsets, views, status, permissions
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from users.models import UserProfile
from users.serializers import UserProfileSerializer
from .models import ProfileMedia, KYCSubmission, Interest, Language, Sport, Hobby
from .serializers import ProfileMediaSerializer, KYCSubmissionSerializer
from .services import ProfileCompletionService
from analytics.models import UserJourneyEvent

class ProfileViewSet(viewsets.ModelViewSet):
    """
    Bien que l'essentiel soit géré dans users.views pour /me/, on peut
    avoir des vues dédiées ici pour les manipulations complexes du profil.
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

class ProfileCompletionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        completion_data = ProfileCompletionService.calculate_completion(profile)
        return Response(completion_data)

class ProfileMediaViewSet(viewsets.ModelViewSet):
    serializer_class = ProfileMediaSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return ProfileMedia.objects.filter(profile=profile)

    def perform_create(self, serializer):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        # Si c'est le premier média, le marquer comme primary
        is_primary = not ProfileMedia.objects.filter(profile=profile).exists()
        serializer.save(profile=profile, is_primary=is_primary)

class KYCSubmissionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        try:
            submission = profile.kyc_submission
            serializer = KYCSubmissionSerializer(submission)
            return Response(serializer.data)
        except KYCSubmission.DoesNotExist:
            return Response({"status": "NOT_SUBMITTED"})

    def post(self, request):
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        submission, sub_created = KYCSubmission.objects.get_or_create(profile=profile)
        
        serializer = KYCSubmissionSerializer(submission, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(status='PENDING_REVIEW')
            
            # Emit Analytics Event
            UserJourneyEvent.objects.create(
                user=request.user,
                event_type='KYC_SUBMITTED'
            )
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class KYCAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    queryset = KYCSubmission.objects.all().order_by('-updated_at')
    serializer_class = KYCSubmissionSerializer
    
    def get_queryset(self):
        status_filter = self.request.query_params.get('status')
        if status_filter:
            return self.queryset.filter(status=status_filter)
        return self.queryset

    def update(self, request, *args, **kwargs):
        # Allow updating status
        instance = self.get_object()
        new_status = request.data.get('status')
        if new_status and new_status in dict(KYCSubmission.STATUS_CHOICES).keys():
            instance.status = new_status
            instance.save()
            
            # Synchroniser le statut dénormalisé sur UserProfile
            instance.profile.kyc_status = new_status
            instance.profile.save()

            if new_status == 'APPROVED':
                UserJourneyEvent.objects.create(
                    user=instance.profile.user,
                    event_type='KYC_APPROVED'
                )
            elif new_status == 'REJECTED' or new_status == 'MORE_INFORMATION_REQUIRED':
                UserJourneyEvent.objects.create(
                    user=instance.profile.user,
                    event_type='KYC_REJECTED'
                )

            return Response(KYCSubmissionSerializer(instance).data)
        return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)

class ReferenceDataView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({
            "interests": [{"id": i.id, "label": i.name} for i in Interest.objects.filter(is_active=True)],
            "languages": [{"id": l.id, "label": l.name} for l in Language.objects.all()],
            "sports": [{"id": s.id, "label": s.name} for s in Sport.objects.all()],
            "hobbies": [{"id": h.id, "label": h.name} for h in Hobby.objects.all()]
        })
