import requests
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, UserProfile
from .serializers import UserSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get', 'put', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        user = request.user
        if request.method == 'GET':
            serializer = self.get_serializer(user)
            return Response(serializer.data)
        elif request.method in ['PUT', 'PATCH']:
            # Permettre de forcer la création du profil s'il n'existait pas
            UserProfile.objects.get_or_create(user=user)
            serializer = self.get_serializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def discover(self, request):
        """Retourne les profils potentiels (qui ne sont pas dans mes relations Match)"""
        user = request.user
        from django.db.models import Q
        from matchmaking.models import Match
        
        # Trouver tous les IDs concernés par un match existant
        matches = Match.objects.filter(Q(user1=user) | Q(user2=user))
        matched_user_ids = []
        for m in matches:
            matched_user_ids.append(m.user1.id if m.user2 == user else m.user2.id)
            
        # Exclure soit-même et les profils déjà matchés
        potential_users = User.objects.filter(is_verified=True).exclude(id=user.id).exclude(id__in=matched_user_ids)
        
        serializer = self.get_serializer(potential_users, many=True)
        return Response(serializer.data)

class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        access_token = request.data.get('access_token')
        if not access_token:
            return Response({'error': 'Token Google manquant'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Vérifier le token auprès de l'API Google UserInfo
            google_response = requests.get(
                'https://www.googleapis.com/oauth2/v3/userinfo',
                params={'access_token': access_token}
            )
            
            if google_response.status_code != 200:
                return Response({'error': 'Token Google invalide ou expiré'}, status=status.HTTP_401_UNAUTHORIZED)
            
            user_info = google_response.json()
            email = user_info.get('email')
            first_name = user_info.get('given_name', '')
            last_name = user_info.get('family_name', '')
            picture = user_info.get('picture', '')

            if not email:
                return Response({'error': 'Impossible de récupérer l\'email via Google'}, status=status.HTTP_400_BAD_REQUEST)

            # Get or Create User
            user, created = User.objects.get_or_create(username=email, defaults={
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'is_verified': True
            })

            # Ensure profile exists
            UserProfile.objects.get_or_create(user=user)

            # Generate internal JWT Tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                    'picture': picture
                }
            })

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
