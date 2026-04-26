from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Match, Message
from .serializers import MatchSerializer, MessageSerializer

class MatchViewSet(viewsets.ModelViewSet):
    serializer_class = MatchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Match.objects.filter(Q(user1=user) | Q(user2=user))

    @action(detail=False, methods=['post'])
    def like(self, request):
        target_id = request.data.get('target_user_id')
        user = request.user

        if str(target_id) == str(user.id):
            return Response({'error': 'Opération non autorisée.'}, status=status.HTTP_400_BAD_REQUEST)

        match = Match.objects.filter(
            (Q(user1=user) & Q(user2_id=target_id)) | 
            (Q(user1_id=target_id) & Q(user2=user))
        ).first()

        if match:
            if match.user2 == user and not match.is_accepted:
                # C'est un MATCH confirmé !
                match.is_accepted = True
                match.save()
                return Response({'status': 'matched', 'match_id': match.id}, status=status.HTTP_200_OK)
            return Response({'status': 'already_liked', 'match_id': match.id}, status=status.HTTP_200_OK)
        
        # Envoi d'un like initial
        match = Match.objects.create(user1=user, user2_id=target_id, is_accepted=False)
        return Response({'status': 'liked', 'match_id': match.id}, status=status.HTTP_201_CREATED)

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
        serializer.save(sender=self.request.user)
