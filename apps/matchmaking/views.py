from rest_framework import viewsets, permissions, status, views
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q
from users.models import UserProfile, User
from .models import Match, Message, SwipeAction, MatchCandidate, SuggestionStatus
from .serializers import MatchSerializer, MessageSerializer
from .services import MatchingScoreService, CompatibilityService, DiscoveryFallbackService
from analytics.models import UserJourneyEvent
from django.core.cache import cache
import uuid

class SuggestionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Anti-Burn Matching : Rate Limiting
        # Vérification du nombre de swipes aujourd'hui
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        daily_swipes = SwipeAction.objects.filter(
            sender=user, 
            timestamp__date=today
        ).count()
        
        # Limite = 30 pour Free (on hardcode pour l'instant)
        LIMIT = 30
        if daily_swipes >= LIMIT:
            UserJourneyEvent.objects.create(user=user, event_type='DISCOVERY_LIMIT_REACHED')
            reset_time = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return Response({
                "limit_reached": True,
                "remaining": 0,
                "reset_at": reset_time.isoformat()
            })
            
        # 1. Check Redis Queue
        queue_key = f"user_match_queue:{user.id}"
        cached_candidates = cache.get(queue_key)
        
        if not cached_candidates:
            UserJourneyEvent.objects.create(user=user, event_type='MATCH_QUEUE_EMPTY')
            # Cold Start Engine
            raw_candidates = DiscoveryFallbackService.get_fallback_candidates(user, limit=10)
            cached_candidates = []
            
            for candidate in raw_candidates:
                # Calculer score
                score_data = MatchingScoreService.calculate_score(user, candidate)
                # Formater Frontend
                compat_data = CompatibilityService.format_for_frontend(score_data)
                
                # Créer MatchCandidate historisé
                candidate_obj, created = MatchCandidate.objects.get_or_create(
                    user=user,
                    candidate=candidate,
                    defaults={
                        'compatibility_score': score_data,
                        'status': SuggestionStatus.NEW
                    }
                )
                
                # Fetch profile info
                profile = getattr(candidate, 'profile', None)
                
                profile_data = {}
                if profile:
                    # Simulation d'une photo principale et du compte de photos
                    # Dans le futur, on ira chercher dans ProfileMedia
                    from profiles.models import ProfileMedia
                    media = ProfileMedia.objects.filter(profile=profile, is_primary=True).first()
                    media_count = ProfileMedia.objects.filter(profile=profile).count()
                    
                    profile_data = {
                        "first_name": candidate.first_name or candidate.username,
                        "age": profile.age() if hasattr(profile, 'age') else None,
                        "city": getattr(profile, 'city', profile.country_code),
                        "kyc_verified": profile.kyc_status == 'APPROVED',
                        "primary_photo": media.file.url if media else None,
                        "photos_count": media_count
                    }
                else:
                    profile_data = {
                        "first_name": candidate.username,
                        "age": None,
                        "city": None,
                        "kyc_verified": False,
                        "primary_photo": None,
                        "photos_count": 0
                    }

                # Renvoyer au frontend
                cached_candidates.append({
                    "id": candidate_obj.id, # ID de la suggestion (MatchCandidate)
                    "candidate_id": candidate.id,
                    "feed_version": candidate_obj.feed_version,
                    "compatibility": compat_data.get("compatibility", 0),
                    "compatibility_explanation": compat_data.get("explanation", {}),
                    "compatibility_breakdown": compat_data.get("breakdown", {}),
                    "highlights": compat_data.get("highlights", []),
                    "profile": profile_data
                })
            
            # Stocker dans Redis pour 1 heure
            cache.set(queue_key, cached_candidates, 3600)
            
        return Response({
            "status": "success",
            "suggestions": cached_candidates
        })

class SwipeActionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        sender = request.user
        receiver_id = request.data.get('target_user_id')
        action = request.data.get('action') # LIKE, PASS, SUPER_LIKE
        
        if not receiver_id or action not in ['LIKE', 'PASS', 'SUPER_LIKE']:
            return Response({"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)
            
        if str(receiver_id) == str(sender.id):
            return Response({"error": "Cannot swipe yourself"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            receiver = User.objects.get(id=receiver_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            # 1. Créer le SwipeAction
            swipe, created = SwipeAction.objects.get_or_create(
                sender=sender,
                receiver=receiver,
                defaults={'action': action}
            )
            
            if not created:
                return Response({"error": "Already swiped"}, status=status.HTTP_400_BAD_REQUEST)

            # 2. Update MatchCandidate status
            MatchCandidate.objects.filter(user=sender, candidate=receiver).update(
                status=SuggestionStatus.LIKED if action in ['LIKE', 'SUPER_LIKE'] else SuggestionStatus.PASSED
            )

            # 3. Analytics
            UserJourneyEvent.objects.create(
                user=sender,
                event_type=f'PROFILE_{action}'
            )

            # 4. Check for Match (Si l'autre a déjà liké)
            if action in ['LIKE', 'SUPER_LIKE']:
                mutual_like = SwipeAction.objects.filter(
                    sender=receiver,
                    receiver=sender,
                    action__in=['LIKE', 'SUPER_LIKE']
                ).exists()

                if mutual_like:
                    # MATCH !
                    # Calculate final compatibility score
                    score_data = MatchingScoreService.calculate_score(sender, receiver)
                    
                    match = Match.objects.create(
                        user1=sender,
                        user2=receiver,
                        is_accepted=True,
                        conversation_id=str(uuid.uuid4()), # Placeholder Chat Sprint 5
                        compatibility_score=score_data['score'],
                        compatibility_breakdown=score_data['breakdown']
                    )
                    
                    MatchCandidate.objects.filter(
                        Q(user=sender, candidate=receiver) | Q(user=receiver, candidate=sender)
                    ).update(status=SuggestionStatus.MATCHED)
                    
                    UserJourneyEvent.objects.create(user=sender, event_type='MATCH_CREATED')
                    UserJourneyEvent.objects.create(user=receiver, event_type='MATCH_CREATED')
                    
                    # Notification MATCH (TODO: Brancher le NotificationService)
                    
                    # Invalidate Redis queues
                    cache.delete(f"user_match_queue:{sender.id}")
                    cache.delete(f"user_match_queue:{receiver.id}")
                    
                    return Response({"status": "matched", "match_id": match.id})

            # Invalidate Redis queue to refresh candidates next time if needed
            # Remove this candidate from the cached queue
            queue_key = f"user_match_queue:{sender.id}"
            cached_candidates = cache.get(queue_key)
            if cached_candidates:
                filtered = [c for c in cached_candidates if c['id'] != int(receiver_id)]
                cache.set(queue_key, filtered, 3600)

            return Response({"status": "success", "action": action})

class MatchViewSet(viewsets.ModelViewSet):
    serializer_class = MatchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Match.objects.filter(Q(user1=user) | Q(user2=user)).filter(is_rejected=False)

class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        match_id = self.request.query_params.get('match_id')
        queryset = Message.objects.filter(Q(match__user1=user) | Q(match__user2=user))
        
        if match_id:
            queryset = queryset.filter(match_id=match_id)
            
        return queryset.order_by('timestamp')
        
    def perform_create(self, serializer):
        message = serializer.save(sender=self.request.user)
        match = message.match
        
        # Determine the recipient
        receiver = match.user2 if match.user1 == self.request.user else match.user1
        
        # Send WS notification via Channels
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{receiver.id}_notifications",
                {
                    "type": "notification_message",
                    "message": {
                        "type": "NEW_MESSAGE",
                        "title": f"Nouveau message de {self.request.user.first_name}",
                        "message": message.content,
                        "relatedEntityId": match.id
                    }
                }
            )
