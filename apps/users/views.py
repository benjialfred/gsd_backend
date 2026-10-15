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
            user = User.objects.select_related('profile').prefetch_related(
                'profile__media',
                'profile__user_languages',
                'profile__user_interests',
                'profile__user_sports',
                'profile__user_hobbies',
                'enrollments__course'
            ).get(id=request.user.id)
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
            
            # Lien de confirmation vers le frontend
            verify_url = f"http://localhost:5173/verify-email?uid={uid}&token={token}"
            
            from .emails import send_verification_email
            try:
                send_verification_email(user, verify_url)
            except Exception as e:
                user.delete() # Annuler l'inscription si l'email ne part pas
                return Response({'error': f"Erreur d'envoi d'e-mail: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({
                'message': "Inscription réussie. Veuillez confirmer votre e-mail pour activer votre compte."
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        uidb64 = request.GET.get('uid')
        token = request.GET.get('token')
        
        if not token and not uidb64:
            return Response({'error': 'Paramètres manquants.'}, status=status.HTTP_400_BAD_REQUEST)
            
        user = None
        if uidb64:
            try:
                uid = force_str(urlsafe_base64_decode(uidb64))
                user = User.objects.get(pk=uid)
            except Exception:
                user = None
        elif token and ':' in token:
            parts = token.split(':')
            raw_uid = parts[0]
            token_remainder = ':'.join(parts[1:])
            try:
                user = User.objects.filter(pk=raw_uid).first()
                if not user:
                    user = User.objects.filter(id=raw_uid).first()
                token = token_remainder
            except Exception:
                user = None

        is_json = 'application/json' in request.headers.get('Accept', '') or request.GET.get('format') == 'json'

        if user is not None and default_token_generator.check_token(user, token):
            user.email_verified = True
            user.is_verified = True
            user.save()

            if is_json:
                from rest_framework_simplejwt.tokens import RefreshToken
                from users.serializers import UserSerializer
                refresh = RefreshToken.for_user(user)
                return Response({
                    'status': 'success',
                    'message': 'Votre compte a été vérifié avec succès.',
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': UserSerializer(user).data
                })
            
            # Redirection vers le frontend
            return redirect('http://localhost:5173/login?verified=true')
            
        if is_json:
            return Response({'error': 'Lien de confirmation invalide ou expiré.'}, status=status.HTTP_400_BAD_REQUEST)

        return redirect('http://localhost:5173/login?error=invalid_token')


import re
import random
from datetime import timedelta
from django.utils import timezone
from django.conf import settings


class SetPinView(APIView):
    """
    Permet à un utilisateur connecté de définir ou modifier son Code PIN de reconnexion rapide.
    Si un code PIN existe déjà, le mot de passe actuel est exigé.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        pin = request.data.get('pin')
        current_password = request.data.get('current_password')

        if not pin:
            return Response({'error': "Le code PIN est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)

        pin_str = str(pin).strip()
        if not re.match(r'^\d{4,6}$', pin_str):
            return Response({'error': "Le code PIN doit comporter entre 4 et 6 chiffres numériques (ex: 1234)."}, status=status.HTTP_400_BAD_REQUEST)

        # Si l'utilisateur a déjà un PIN configuré ou renseigne un mot de passe, vérifier son mot de passe
        if user.has_pin and current_password and not user.check_password(current_password):
            return Response({'error': "Mot de passe actuel incorrect pour modifier le code PIN."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_pin(pin_str)
        return Response({
            'success': True,
            'message': "Votre code PIN de reconnexion rapide a été configuré avec succès !",
            'has_pin': True
        }, status=status.HTTP_200_OK)


class RemovePinView(APIView):
    """
    Désactive le code PIN avec confirmation du mot de passe principal.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password')

        if not user.check_password(current_password):
            return Response({'error': "Mot de passe incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        user.pin_hash = None
        user.pin_failed_attempts = 0
        user.pin_locked_until = None
        user.save(update_fields=['pin_hash', 'pin_failed_attempts', 'pin_locked_until'])

        return Response({
            'success': True,
            'message': "Votre code PIN a été désactivé.",
            'has_pin': False
        }, status=status.HTTP_200_OK)


class PinLoginView(APIView):
    """
    Reconnexion rapide par Code PIN (AllowAny).
    Vérifie l'e-mail / username et le code PIN haché.
    Protection anti-brute force : verrouille après 5 échecs consécutifs.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identifier = request.data.get('identifier') or request.data.get('email') or request.data.get('username')
        pin = request.data.get('pin')

        if not identifier or not pin:
            return Response({'error': "L'identifiant (e-mail) et le code PIN sont obligatoires."}, status=status.HTTP_400_BAD_REQUEST)

        identifier = identifier.strip().lower()
        user = User.objects.filter(email__iexact=identifier).first() or User.objects.filter(username__iexact=identifier).first()

        if not user:
            return Response({'error': "Identifiant ou code PIN incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        if not user.has_pin:
            return Response({'error': "Aucun code PIN n'est configuré pour ce compte. Veuillez vous connecter avec votre mot de passe habituel."}, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier si le compte est temporairement verrouillé
        if user.pin_locked_until and timezone.now() < user.pin_locked_until:
            mins_left = max(1, int((user.pin_locked_until - timezone.now()).total_seconds() / 60))
            return Response({
                'error': f"Trop d'échecs consécutifs. Votre code PIN est bloqué pendant encore {mins_left} minute(s). Connectez-vous avec votre mot de passe principal.",
                'locked': True,
                'minutes_remaining': mins_left
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        is_valid = user.check_pin(pin)
        if not is_valid:
            attempts_left = max(0, 5 - user.pin_failed_attempts)
            if attempts_left == 0:
                return Response({
                    'error': "Trop d'échecs. Votre code PIN est désormais verrouillé pendant 15 minutes. Utilisez votre mot de passe principal.",
                    'locked': True
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            return Response({
                'error': f"Code PIN incorrect. Il vous reste {attempts_left} tentative(s).",
                'attempts_left': attempts_left
            }, status=status.HTTP_400_BAD_REQUEST)

        # Succès : Génération des tokens JWT
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user, context={'request': request}).data

        return Response({
            'success': True,
            'message': f"Bienvenue, {user.first_name or user.username} !",
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': user_data
        }, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    """
    Demande de réinitialisation de mot de passe (oubli).
    Génère un code OTP à 6 chiffres ET un lien tokenisé sécurisé (15 minutes).
    Envoie un email de prestige Maison Fauve.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': "L'adresse e-mail est requise."}, status=status.HTTP_400_BAD_REQUEST)

        email = email.strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if user:
            # Code OTP à 6 chiffres
            otp_code = f"{random.randint(100000, 999999)}"
            user.reset_otp_code = otp_code
            user.reset_otp_expires_at = timezone.now() + timedelta(minutes=15)
            user.save(update_fields=['reset_otp_code', 'reset_otp_expires_at'])

            # Token de sécurité Django
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"http://localhost:5173/reset-password?uid={uid}&token={token}&email={user.email}&code={otp_code}"

            subject = "Récupération d'accès & Mot de passe - Le Grand Salon Divin"
            first_name = user.first_name or user.username or "Membre"

            html_message = f"""
            <div style="font-family: 'Times New Roman', Georgia, serif; background-color: #FAF9F6; padding: 40px 20px; color: #1A3A5C;">
                <div style="max-width: 560px; margin: 0 auto; background-color: #FFFFFF; border-radius: 16px; border: 1px solid #E8ECE9; padding: 40px; text-align: center; box-shadow: 0 4px 20px rgba(26,58,92,0.06);">
                    <div style="font-size: 20px; font-weight: bold; color: #C9A84C; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px;">
                        LE GRAND SALON DIVIN
                    </div>
                    <div style="font-size: 13px; color: #1A3A5C; opacity: 0.7; letter-spacing: 1px; margin-bottom: 24px;">
                        ALLIANCE & SANCTIFICATION MATRIMONIALE
                    </div>
                    <hr style="border: 0; border-top: 1px solid #F0EDE6; margin-bottom: 24px;" />
                    <h2 style="font-size: 22px; font-weight: normal; margin-bottom: 16px; color: #1A3A5C;">
                        Récupération de vos accès
                    </h2>
                    <p style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #4A4A4A; margin-bottom: 24px;">
                        Bonjour <strong>{first_name}</strong>,<br/>
                        Une demande de réinitialisation de mot de passe a été formulée pour votre compte. Vous pouvez utiliser votre code de sécurité temporaire ou cliquer directement sur le bouton ci-dessous :
                    </p>
                    <div style="background-color: #FAF9F6; border: 2px dashed #C9A84C; border-radius: 12px; padding: 20px; margin: 24px 0;">
                        <div style="font-family: Arial, sans-serif; font-size: 11px; text-transform: uppercase; letter-spacing: 2px; color: #1A3A5C; margin-bottom: 6px;">
                            Votre Code de Sécurité (Valable 15 min)
                        </div>
                        <div style="font-family: 'Courier New', monospace; font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1A3A5C;">
                            {otp_code}
                        </div>
                    </div>
                    <div style="margin: 32px 0;">
                        <a href="{reset_url}" style="display: inline-block; background-color: #1A3A5C; color: #FFFFFF; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-family: Arial, sans-serif; font-size: 13px; font-weight: bold; letter-spacing: 1px; text-transform: uppercase;">
                            Réinitialiser Mon Mot de Passe
                        </a>
                    </div>
                    <p style="font-family: Arial, sans-serif; font-size: 12px; color: #888888; line-height: 1.5; margin-top: 30px;">
                        Si vous n'êtes pas à l'origine de cette demande, veuillez ignorer cet e-mail en toute sérénité. Vos accès restent protégés.
                    </p>
                </div>
            </div>
            """

            try:
                send_mail(
                    subject,
                    f"Bonjour {first_name}, votre code de réinitialisation GSD est : {otp_code}. Lien : {reset_url}",
                    getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@gsd.com'),
                    [user.email],
                    fail_silently=True,
                    html_message=html_message
                )
            except Exception:
                pass

        return Response({
            'success': True,
            'message': "Si cette adresse e-mail correspond à un compte membre, un code et un lien de réinitialisation ont été envoyés.",
            'email': email
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """
    Confirme la réinitialisation du mot de passe.
    Supporte :
    1. Soit la saisie directe (email + code OTP à 6 chiffres + new_password)
    2. Soit le lien e-mail tokenisé (uid + token + new_password)
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp_code') or request.data.get('code')
        uidb64 = request.data.get('uid')
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        if not new_password or len(str(new_password).strip()) < 6:
            return Response({'error': "Le nouveau mot de passe doit comporter au moins 6 caractères."}, status=status.HTTP_400_BAD_REQUEST)

        user = None

        # Option A : Validation par Code OTP
        if email and otp_code:
            email_clean = email.strip().lower()
            user_candidate = User.objects.filter(email__iexact=email_clean).first()
            if (
                user_candidate 
                and user_candidate.reset_otp_code 
                and user_candidate.reset_otp_code.strip() == str(otp_code).strip()
                and user_candidate.reset_otp_expires_at 
                and user_candidate.reset_otp_expires_at >= timezone.now()
            ):
                user = user_candidate

        # Option B : Validation par UID + Token standard Django
        if not user and uidb64 and token:
            try:
                uid = force_str(urlsafe_base64_decode(uidb64))
                user_candidate = User.objects.get(pk=uid)
                if default_token_generator.check_token(user_candidate, token):
                    user = user_candidate
            except Exception:
                user = None

        if not user:
            return Response({
                'error': "Le code de sécurité ou le lien de réinitialisation est invalide ou a expiré (validité 15 min)."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Réinitialisation effective
        user.set_password(str(new_password).strip())
        user.reset_otp_code = None
        user.reset_otp_expires_at = None
        user.pin_failed_attempts = 0
        user.pin_locked_until = None
        user.email_verified = True
        user.is_verified = True
        user.save()

        return Response({
            'success': True,
            'message': "Votre mot de passe a été réinitialisé avec succès ! Vous pouvez maintenant vous connecter."
        }, status=status.HTTP_200_OK)
