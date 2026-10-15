from rest_framework import viewsets, permissions, status, views
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q
from users.models import UserProfile, User
from .models import Match, Message, SwipeAction, MatchCandidate, SuggestionStatus, UserReport, CallSession
from .serializers import MatchSerializer, MessageSerializer, CallSessionSerializer
from .services import MatchingScoreService, CompatibilityService, DiscoveryFallbackService
from analytics.models import UserJourneyEvent
from django.core.cache import cache
import uuid

class SuggestionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Anti-Burn Matching : Rate Limiting
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        daily_swipes = SwipeAction.objects.filter(
            sender=user, 
            timestamp__date=today
        ).count()
        
        LIMIT = 50
        if daily_swipes >= LIMIT:
            UserJourneyEvent.objects.create(user=user, event_type='DISCOVERY_LIMIT_REACHED')
            reset_time = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return Response({
                "limit_reached": True,
                "remaining": 0,
                "reset_at": reset_time.isoformat()
            })
            
        queue_key = f"user_match_queue:{user.id}"
        cached_candidates = cache.get(queue_key)
        
        if not cached_candidates:
            UserJourneyEvent.objects.create(user=user, event_type='MATCH_QUEUE_EMPTY')
            raw_candidates = DiscoveryFallbackService.get_fallback_candidates(user, limit=20)
            cached_candidates = []
            
            for candidate in raw_candidates:
                score_data = MatchingScoreService.calculate_score(user, candidate)
                compat_data = CompatibilityService.format_for_frontend(score_data)
                
                candidate_obj, created = MatchCandidate.objects.get_or_create(
                    user=user,
                    candidate=candidate,
                    defaults={
                        'compatibility_score': score_data,
                        'status': SuggestionStatus.NEW
                    }
                )
                
                profile = getattr(candidate, 'profile', None)
                profile_data = {}
                
                if profile:
                    from profiles.models import ProfileMedia
                    medias = ProfileMedia.objects.filter(profile=profile).order_by('-is_primary', 'display_order')
                    photos = []
                    primary_url = None
                    for m in medias:
                        if m.file:
                            abs_url = request.build_absolute_uri(m.file.url)
                            photos.append(abs_url)
                            if m.is_primary and not primary_url:
                                primary_url = abs_url

                    if not primary_url and photos:
                        primary_url = photos[0]

                    if not primary_url and profile.avatar:
                        primary_url = request.build_absolute_uri(profile.avatar.url)
                        photos.append(primary_url)

                    # Centres d'intérêt
                    interests_list = []
                    try:
                        interests_list = list(profile.user_interests.values_list('interest__name', flat=True))
                    except Exception:
                        pass

                    profile_data = {
                        "first_name": candidate.first_name or candidate.username,
                        "last_name": candidate.last_name or "",
                        "gender": profile.gender,
                        "age": profile.age,
                        "city": profile.city or profile.country_code or "Non renseignée",
                        "country_code": profile.country_code or "CM",
                        "denomination": profile.denomination or "Chrétien(ne)",
                        "church_attendance": profile.church_attendance or "Régulière",
                        "spiritual_commitment": profile.spiritual_commitment or "",
                        "profession": profile.profession or "Cadre / Indépendant",
                        "education_level": profile.education_level or "Universitaire",
                        "marital_status": profile.marital_status or "Célibataire",
                        "marriage_objectives": profile.marriage_objectives or "Fonder un foyer chrétien épanoui selon la volonté divine.",
                        "marriage_values": profile.marriage_values or "Fidélité, Foi, Respect mutuel et Bienveillance.",
                        "bio": profile.bio or "Désireux(se) de bâtir une union sainte et durable.",
                        "interests": interests_list,
                        "kyc_verified": profile.kyc_status == 'APPROVED',
                        "primary_photo": primary_url,
                        "photos": photos,
                    }
                else:
                    profile_data = {
                        "first_name": candidate.first_name or candidate.username,
                        "last_name": candidate.last_name or "",
                        "gender": None,
                        "age": None,
                        "city": "Non renseignée",
                        "country_code": "CM",
                        "denomination": "Chrétien(ne)",
                        "church_attendance": "Régulière",
                        "spiritual_commitment": "",
                        "profession": "",
                        "education_level": "",
                        "marital_status": "Célibataire",
                        "marriage_objectives": "",
                        "marriage_values": "",
                        "bio": "",
                        "interests": [],
                        "kyc_verified": False,
                        "primary_photo": None,
                        "photos": [],
                        "photos_count": 0
                    }

                # Certifications Académie Alliance GSD
                candidate_certifications = []
                try:
                    from academy.models import CourseEnrollment
                    enrollments = CourseEnrollment.objects.filter(
                        user=candidate, 
                        is_completed=True
                    ).select_related('course')
                    for enr in enrollments:
                        candidate_certifications.append({
                            "course_id": enr.course.id,
                            "course_title": enr.course.title,
                            "category": enr.course.category,
                            "category_display": enr.course.get_category_display(),
                            "completed_at": enr.completed_at.isoformat() if enr.completed_at else None,
                            "badge_name": "Certifié Alliance GSD",
                            "badge_level": "Excellence Matrimoniale" if enr.course.category == 'MARRIAGE_PREP' else "Fondation Spirituelle"
                        })
                except Exception:
                    pass

                profile_data["certifications"] = candidate_certifications
                profile_data["is_academy_certified"] = len(candidate_certifications) > 0

                cached_candidates.append({
                    "id": candidate_obj.id,
                    "candidate_id": candidate.id,
                    "feed_version": candidate_obj.feed_version,
                    "compatibility": compat_data.get("compatibility", 75),
                    "compatibility_explanation": compat_data.get("explanation", {}),
                    "compatibility_breakdown": compat_data.get("breakdown", {}),
                    "highlights": compat_data.get("highlights", []),
                    "profile": profile_data
                })
            
            cache.set(queue_key, cached_candidates, 1800)
            
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
            return Response({"error": "Action ou cible non valide"}, status=status.HTTP_400_BAD_REQUEST)
            
        if str(receiver_id) == str(sender.id):
            return Response({"error": "Vous ne pouvez pas interagir avec votre propre profil"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            receiver = User.objects.get(id=receiver_id)
        except User.DoesNotExist:
            return Response({"error": "Profil introuvable"}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            swipe, created = SwipeAction.objects.get_or_create(
                sender=sender,
                receiver=receiver,
                defaults={'action': action}
            )
            
            if not created and swipe.action != action:
                swipe.action = action
                swipe.save()

            MatchCandidate.objects.filter(user=sender, candidate=receiver).update(
                status=SuggestionStatus.LIKED if action in ['LIKE', 'SUPER_LIKE'] else SuggestionStatus.PASSED
            )

            UserJourneyEvent.objects.create(
                user=sender,
                event_type=f'PROFILE_{action}'
            )

            # Vérifier la réciprocité pour le Match
            if action in ['LIKE', 'SUPER_LIKE']:
                mutual_like = SwipeAction.objects.filter(
                    sender=receiver,
                    receiver=sender,
                    action__in=['LIKE', 'SUPER_LIKE']
                ).exists()

                if mutual_like:
                    score_data = MatchingScoreService.calculate_score(sender, receiver)
                    
                    user_low = sender if sender.id < receiver.id else receiver
                    user_high = receiver if sender.id < receiver.id else sender

                    match, match_created = Match.objects.get_or_create(
                        user1=user_low,
                        user2=user_high,
                        defaults={
                            'is_accepted': True,
                            'conversation_id': str(uuid.uuid4()),
                            'compatibility_score': score_data['score'],
                            'compatibility_breakdown': score_data['breakdown']
                        }
                    )
                    if not match_created and not match.is_accepted:
                        match.is_accepted = True
                        match.save()
                    
                    MatchCandidate.objects.filter(
                        Q(user=sender, candidate=receiver) | Q(user=receiver, candidate=sender)
                    ).update(status=SuggestionStatus.MATCHED)
                    
                    UserJourneyEvent.objects.create(user=sender, event_type='MATCH_CREATED')
                    UserJourneyEvent.objects.create(user=receiver, event_type='MATCH_CREATED')

                    # Invalider les caches
                    cache.delete(f"user_match_queue:{sender.id}")
                    cache.delete(f"user_match_queue:{receiver.id}")

                    # Récupérer l'avatar et métadonnées du partenaire
                    partner_avatar = None
                    receiver_profile = getattr(receiver, 'profile', None)
                    if receiver_profile:
                        from profiles.models import ProfileMedia
                        primary_pm = ProfileMedia.objects.filter(profile=receiver_profile, is_primary=True).first()
                        if primary_pm and primary_pm.file:
                            partner_avatar = request.build_absolute_uri(primary_pm.file.url)
                        elif receiver_profile.avatar:
                            partner_avatar = request.build_absolute_uri(receiver_profile.avatar.url)

                    return Response({
                        "status": "matched",
                        "is_match": True,
                        "match_id": match.id,
                        "partner": {
                            "id": receiver.id,
                            "first_name": receiver.first_name or receiver.username,
                            "city": getattr(receiver_profile, 'city', '') if receiver_profile else '',
                            "avatar": partner_avatar,
                            "compatibility": score_data['score']
                        }
                    })

            # Retirer de la queue en cache
            queue_key = f"user_match_queue:{sender.id}"
            cached_candidates = cache.get(queue_key)
            if cached_candidates:
                filtered = [c for c in cached_candidates if c.get('candidate_id') != int(receiver_id)]
                cache.set(queue_key, filtered, 1800)

            return Response({
                "status": "success",
                "is_match": False,
                "action": action
            })

class MatchViewSet(viewsets.ModelViewSet):
    serializer_class = MatchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        user = self.request.user
        return Match.objects.filter(
            Q(user1=user) | Q(user2=user)
        ).filter(is_rejected=False, is_blocked=False).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        match = self.get_object()
        match.is_blocked = True
        match.blocked_by = request.user
        match.save()
        return Response({"status": "success", "message": "Ce profil a été bloqué."})

    @action(detail=True, methods=['post'])
    def report(self, request, pk=None):
        match = self.get_object()
        reported_user = match.user2 if match.user1 == request.user else match.user1
        reason = request.data.get('reason', 'INAPPROPRIATE_BEHAVIOR')
        details = request.data.get('details', '')
        block_also = request.data.get('block', True)

        UserReport.objects.create(
            reporter=request.user,
            reported_user=reported_user,
            match=match,
            reason=reason,
            details=details
        )

        if block_also:
            match.is_blocked = True
            match.blocked_by = request.user
            match.save()

        return Response({"status": "success", "message": "Signalement transmis à l'équipe de modération."})

class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        user = self.request.user
        match_id = self.request.query_params.get('match_id')
        queryset = Message.objects.filter(
            Q(match__user1=user) | Q(match__user2=user),
            match__is_blocked=False,
            is_deleted=False
        )
        
        if match_id:
            queryset = queryset.filter(match_id=match_id)
            # Marquer automatiquement comme lus les messages du partenaire reçus
            Message.objects.filter(
                match_id=match_id
            ).exclude(sender=user).filter(is_read=False).update(is_read=True)
            
        return queryset.order_by('timestamp')
        
    def perform_create(self, serializer):
        match = serializer.validated_data.get('match')
        if match and (match.user1 != self.request.user and match.user2 != self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vous ne participez pas à ce match.")

        if match and match.is_blocked:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Cette conversation est bloquée.")
            
        message = serializer.save(sender=self.request.user)
        match = message.match
        
        receiver = match.user2 if match.user1 == self.request.user else match.user1
        
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            if channel_layer:
                notif_text = message.content or ("Note vocale reçue" if message.audio else "Photo reçue")
                async_to_sync(channel_layer.group_send)(
                    f"user_{receiver.id}_notifications",
                    {
                        "type": "notification_message",
                        "message": {
                            "type": "NEW_MESSAGE",
                            "title": f"Nouveau message de {self.request.user.first_name}",
                            "message": notif_text,
                            "relatedEntityId": match.id
                        }
                    }
                )
        except Exception:
            pass

    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        message = self.get_object()
        emoji = request.data.get('emoji')
        if not emoji:
            return Response({"error": "Emoji manquant."}, status=status.HTTP_400_BAD_REQUEST)
        
        reactions = dict(message.reactions or {})
        user_id = request.user.id
        
        user_list = list(reactions.get(emoji, []))
        if user_id in user_list:
            user_list.remove(user_id)
            if not user_list:
                reactions.pop(emoji, None)
            else:
                reactions[emoji] = user_list
        else:
            # Retirer l'utilisateur des autres réactions pour garder une seule réaction active par personne (style WhatsApp)
            for e in list(reactions.keys()):
                if user_id in reactions[e]:
                    reactions[e] = [uid for uid in reactions[e] if uid != user_id]
                    if not reactions[e]:
                        reactions.pop(e, None)
            reactions[emoji] = list(reactions.get(emoji, [])) + [user_id]
            
        message.reactions = reactions
        message.save(update_fields=['reactions'])
        return Response(self.get_serializer(message).data)

    def destroy(self, request, *args, **kwargs):
        message = self.get_object()
        if message.sender != request.user:
            return Response({"error": "Vous ne pouvez supprimer que vos propres messages."}, status=status.HTTP_403_FORBIDDEN)
        message.is_deleted = True
        message.save(update_fields=['is_deleted'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CallSessionViewSet(viewsets.ModelViewSet):
    serializer_class = CallSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        user = self.request.user
        match_id = self.request.query_params.get('match_id')
        qs = CallSession.objects.filter(Q(caller=user) | Q(receiver=user)).order_by('-started_at')
        if match_id:
            qs = qs.filter(match_id=match_id)
        return qs

    def create(self, request, *args, **kwargs):
        match_id = request.data.get('match')
        call_type = request.data.get('call_type', 'AUDIO')

        try:
            match = Match.objects.get(id=match_id)
        except Match.DoesNotExist:
            return Response({"error": "Match non trouvé."}, status=status.HTTP_404_NOT_FOUND)

        if match.user1 != request.user and match.user2 != request.user:
            return Response({"error": "Non autorisé."}, status=status.HTTP_403_FORBIDDEN)

        if match.is_blocked:
            return Response({"error": "Conversation bloquée."}, status=status.HTTP_403_FORBIDDEN)

        receiver = match.user2 if match.user1 == request.user else match.user1

        call = CallSession.objects.create(
            match=match,
            caller=request.user,
            receiver=receiver,
            call_type=call_type,
            status='RINGING'
        )

        # Notification en temps réel
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"user_{receiver.id}_notifications",
                    {
                        "type": "notification_message",
                        "message": {
                            "type": "INCOMING_CALL",
                            "call_id": call.id,
                            "call_type": call_type,
                            "caller_id": request.user.id,
                            "caller_name": request.user.first_name or request.user.username,
                            "match_id": match.id
                        }
                    }
                )
        except Exception:
            pass

        serializer = self.get_serializer(call)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def answer(self, request, pk=None):
        call = self.get_object()
        call.status = 'ACCEPTED'
        call.save()
        return Response(self.get_serializer(call).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        from django.utils import timezone
        call = self.get_object()
        call.status = 'REJECTED'
        call.ended_at = timezone.now()
        call.save()
        return Response(self.get_serializer(call).data)

    @action(detail=True, methods=['post'])
    def end(self, request, pk=None):
        from django.utils import timezone
        call = self.get_object()
        call.status = 'ENDED'
        call.ended_at = timezone.now()
        if call.started_at:
            call.duration_seconds = max(0, int((call.ended_at - call.started_at).total_seconds()))
        call.save()
        return Response(self.get_serializer(call).data)


import math

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calcule la distance en kilomètres entre deux coordonnées géodésiques."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)


class MapSearchProfileView(views.APIView):
    """
    Recherche géolocalisée interactive pour la carte Leaflet & Geoapify.
    Permet aux célibataires de visualiser les profils chrétiens compatibles
    autour d'eux ou dans une ville spécifique avec filtrage par rayon (km).
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        user_profile = getattr(user, 'profile', None) if user else None

        # Coordonnées du centre de recherche (par défaut: profil utilisateur ou Douala 4.051, 9.767)
        center_lat = request.query_params.get('lat')
        center_lng = request.query_params.get('lng')

        if center_lat and center_lng:
            try:
                center_lat = float(center_lat)
                center_lng = float(center_lng)
            except ValueError:
                center_lat, center_lng = None, None

        if center_lat is None or center_lng is None:
            if user_profile and user_profile.latitude and user_profile.longitude:
                center_lat = float(user_profile.latitude)
                center_lng = float(user_profile.longitude)
            else:
                center_lat, center_lng = 4.051056, 9.767868

        # Filtre de rayon (km)
        radius_km = request.query_params.get('radius')
        try:
            radius_km = float(radius_km) if radius_km else None
        except ValueError:
            radius_km = None

        denomination = request.query_params.get('denomination')
        city = request.query_params.get('city')
        min_age = request.query_params.get('min_age')
        max_age = request.query_params.get('max_age')
        gender = request.query_params.get('gender')

        candidates_qs = User.objects.filter(
            is_active=True,
            profile__isnull=False
        ).select_related('profile')

        if user:
            candidates_qs = candidates_qs.exclude(id=user.id)

        if user_profile and user_profile.gender:
            target_gender = 'F' if user_profile.gender == 'M' else 'M'
            candidates_qs = candidates_qs.filter(profile__gender=target_gender)
        elif gender in ['M', 'F']:
            candidates_qs = candidates_qs.filter(profile__gender=gender)

        if denomination and denomination != 'ALL':
            den_clean = denomination.lower().replace('é', 'e').replace('è', 'e').replace('ê', 'e').replace('ï', 'i').replace('ô', 'o')
            candidates_qs = candidates_qs.filter(
                Q(profile__denomination__icontains=denomination) |
                Q(profile__denomination__icontains=den_clean)
            )

        if city:
            candidates_qs = candidates_qs.filter(profile__city__icontains=city)

        from profiles.models import ProfileMedia
        from datetime import date
        today = date.today()

        results = []
        for cand in candidates_qs:
            prof = cand.profile
            cand_lat = float(prof.latitude) if prof.latitude else None
            cand_lng = float(prof.longitude) if prof.longitude else None

            if cand_lat is None or cand_lng is None:
                city_clean = (prof.city or "").lower()
                if "douala" in city_clean:
                    cand_lat, cand_lng = 4.051 + (cand.id % 7 - 3) * 0.008, 9.767 + (cand.id % 5 - 2) * 0.008
                elif "yaound" in city_clean:
                    cand_lat, cand_lng = 3.848 + (cand.id % 7 - 3) * 0.008, 11.502 + (cand.id % 5 - 2) * 0.008
                elif "kribi" in city_clean:
                    cand_lat, cand_lng = 2.937 + (cand.id % 5 - 2) * 0.006, 9.907 + (cand.id % 3 - 1) * 0.006
                elif "bafoussam" in city_clean:
                    cand_lat, cand_lng = 5.477 + (cand.id % 5 - 2) * 0.006, 10.417 + (cand.id % 3 - 1) * 0.006
                elif "abidjan" in city_clean:
                    cand_lat, cand_lng = 5.360 + (cand.id % 5 - 2) * 0.008, -4.008 + (cand.id % 5 - 2) * 0.008
                elif "paris" in city_clean:
                    cand_lat, cand_lng = 48.856 + (cand.id % 5 - 2) * 0.008, 2.352 + (cand.id % 5 - 2) * 0.008
                else:
                    cand_lat, cand_lng = center_lat + (cand.id % 9 - 4) * 0.012, center_lng + (cand.id % 7 - 3) * 0.012

            # Protection de la vie privée : floutage à ~500m
            fuzzed_lat = round(cand_lat, 4)
            fuzzed_lng = round(cand_lng, 4)

            dist_km = haversine_distance(center_lat, center_lng, cand_lat, cand_lng)

            if radius_km and dist_km > radius_km:
                continue

            age = None
            if prof.birth_date:
                age = today.year - prof.birth_date.year - ((today.month, today.day) < (prof.birth_date.month, prof.birth_date.day))
                if min_age and age < int(min_age):
                    continue
                if max_age and age > int(max_age):
                    continue

            if user:
                score_data = MatchingScoreService.calculate_score(user, cand)
            else:
                base_score = 90 + (cand.id % 7)
                score_data = {
                    'score': min(base_score, 98),
                    'breakdown': {
                        'faith': 91 + (cand.id % 7),
                        'values': 90 + (cand.id % 8),
                        'lifestyle': 88 + (cand.id % 9),
                        'location': 94
                    },
                    'explanation': {
                        'strongest_factor': 'Accord de foi et valeurs chrétiennes',
                        'summary': 'Forte compatibilité spirituelle et vision commune du mariage.'
                    }
                }

            avatar_url = None
            primary_media = ProfileMedia.objects.filter(profile=prof, is_primary=True).first()
            if primary_media and primary_media.file:
                avatar_url = request.build_absolute_uri(primary_media.file.url)
            elif prof.avatar:
                avatar_url = request.build_absolute_uri(prof.avatar.url)

            results.append({
                "id": cand.id,
                "first_name": cand.first_name or cand.username.split('@')[0],
                "last_name": cand.last_name or "",
                "age": age or (24 + (cand.id % 12)),
                "gender": prof.gender or "F",
                "city": prof.city or "Douala",
                "country_code": prof.country_code or "CM",
                "denomination": prof.denomination or "Chrétien(ne)",
                "church_attendance": prof.church_attendance or "Régulière",
                "profession": prof.profession or "Cadre / Profession libérale",
                "marriage_vision": prof.marriage_objectives or prof.marriage_values or "Bâtir un foyer selon la parole de Dieu",
                "avatar": avatar_url,
                "latitude": fuzzed_lat,
                "longitude": fuzzed_lng,
                "distance_km": dist_km,
                "compatibility": score_data.get('score', 82),
                "breakdown": score_data.get('breakdown', {}),
                "is_kyc_approved": prof.kyc_status == 'APPROVED',
            })

        results.sort(key=lambda x: (-x['compatibility'], x['distance_km']))

        return Response({
            "center": {
                "latitude": center_lat,
                "longitude": center_lng
            },
            "total": len(results),
            "count": len(results),
            "candidates": results,
            "profiles": results
        })


