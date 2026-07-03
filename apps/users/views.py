import requests
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import redirect
from .models import User, UserProfile
from .serializers import UserSerializer, RegisterSerializer
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]


    @action(detail=False, methods=['get', 'put', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        user = request.user
        if request.method == 'GET':
            serializer = self.get_serializer(user)
            return Response(serializer.data)
        elif request.method in ['PUT', 'PATCH']:
            # Permettre de forcer la création du profil s'il n'existait pas
            UserProfile.objects.get_or_create(user=user)
            
            # Reconstruction du dictionnaire imbriqué 'profile' pour le multipart-data
            data = request.data
            # MultiPartParser produit un QueryDict (qui possède l'attribut copy)
            if hasattr(data, 'copy'):
                mutable_data = data.copy()
                profile_dict = {}
                
                # Récupération des champs textes plats préfixés
                for key in list(mutable_data.keys()):
                    if key.startswith('profile.'):
                        sub_key = key.split('profile.')[1]
                        profile_dict[sub_key] = mutable_data.get(key)
                        del mutable_data[key]
                    elif key.startswith('profile['):
                        sub_key = key.split('[')[1].split(']')[0]
                        profile_dict[sub_key] = mutable_data.get(key)
                        del mutable_data[key]
                        
                # Récupération des fichiers préfixés (ex: avatar)
                if request.FILES:
                    for key in list(request.FILES.keys()):
                        if key.startswith('profile.'):
                            sub_key = key.split('profile.')[1]
                            profile_dict[sub_key] = request.FILES.get(key)
                        elif key.startswith('profile['):
                            sub_key = key.split('[')[1].split(']')[0]
                            profile_dict[sub_key] = request.FILES.get(key)
                            
                if profile_dict:
                    # En DRF, pour passer la validation d'un serializer imbriqué,
                    # il faut lui donner un dictionnaire classique.
                    mutable_data['profile'] = profile_dict
                    
                data = mutable_data
                
            serializer = self.get_serializer(user, data=data, partial=True)
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
            
        # Exclure soit-même et les profils déjà matchés. Seuls les profils certifiés KYC sont découvrables.
        potential_users = User.objects.filter(profile__kyc_status='APPROVED').exclude(id=user.id).exclude(id__in=matched_user_ids)
        
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
                'email_verified': True,
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

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Génération du token de confirmation
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Lien de confirmation (backend local)
            verify_url = f"http://localhost:8000/api/users/verify/?uid={uid}&token={token}"
            
            # Envoi du mail console
            subject = "Confirmez votre compte - Le Grand Salon Divin"
            message = (
                f"Bonjour {user.first_name},\n\n"
                f"Merci de vous être inscrit sur Le Grand Salon Divin.\n"
                f"Veuillez confirmer votre compte en cliquant sur le lien suivant :\n"
                f"{verify_url}\n\n"
                f"Que Dieu vous bénisse,\nL'équipe GSD"
            )
            send_mail(
                subject,
                message,
                'no-reply@gsd.com',
                [user.email],
                fail_silently=False,
            )
            
            return Response({
                'message': "Inscription réussie. Veuillez confirmer votre e-mail pour activer votre compte."
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        uidb64 = request.GET.get('uid')
        token = request.GET.get('token')
        
        if not uidb64 or not token:
            return Response({'error': 'Paramètres manquants.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
            
        if user is not None and default_token_generator.check_token(user, token):
            user.email_verified = True
            user.is_verified = True
            user.save()
            # Redirection vers la page de connexion du frontend
            return redirect('http://localhost:5173/login?verified=true')
            
        return Response({'error': 'Lien de confirmation invalide ou expiré.'}, status=status.HTTP_400_BAD_REQUEST)

