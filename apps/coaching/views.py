from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from datetime import datetime

from .models import CoachProfile, AvailabilitySlot, Appointment
from .serializers import CoachProfileSerializer, AvailabilitySlotSerializer, AppointmentSerializer


class IsCoachOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and (request.user.role in ['COACH', 'ADMIN'] or request.user.is_staff)


class CoachProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = CoachProfileSerializer

    def get_queryset(self):
        queryset = CoachProfile.objects.select_related('user').prefetch_related('availability_slots').all()
        specialty = self.request.query_params.get('specialty')
        if specialty:
            queryset = queryset.filter(specialties__icontains=specialty)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(title__icontains=search) |
                Q(specialties__icontains=search)
            )
        return queryset

    @action(detail=False, methods=['get', 'put', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        profile, created = CoachProfile.objects.get_or_create(
            user=request.user,
            defaults={
                'title': "Conseiller Conjugal & Accompagnateur Pastoral",
                'specialties': "Préparation au Mariage, Communication Chrétienne, Sanctification",
            }
        )
        if request.method == 'GET':
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def available_slots(self, request, pk=None):
        coach = self.get_object()
        date_str = request.query_params.get('date') # Format: YYYY-MM-DD
        if not date_str:
            return Response({"error": "Paramètre 'date' requis (YYYY-MM-DD)"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Format de date invalide (attendu: YYYY-MM-DD)"}, status=status.HTTP_400_BAD_REQUEST)

        # Jour de la semaine en Python : 0 = Lundi, 6 = Dimanche
        day_of_week = target_date.weekday()
        slots = coach.availability_slots.filter(day_of_week=day_of_week, is_active=True)

        # Récupérer les RDV déjà pris ce jour-là
        existing_appointments = Appointment.objects.filter(
            coach=coach,
            appointment_date__date=target_date
        ).exclude(status='CANCELLED')

        booked_times = [appt.appointment_date.strftime('%H:%M') for appt in existing_appointments]

        available = []
        for slot in slots:
            time_formatted = slot.start_time.strftime('%H:%M')
            is_booked = time_formatted in booked_times
            available.append({
                "slot_id": slot.id,
                "start_time": time_formatted,
                "end_time": slot.end_time.strftime('%H:%M'),
                "is_available": not is_booked,
            })

        return Response({
            "coach_id": coach.id,
            "date": date_str,
            "day_name": target_date.strftime('%A'),
            "slots": available
        })


class AvailabilitySlotViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AvailabilitySlotSerializer

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'coach_profile'):
            return AvailabilitySlot.objects.filter(coach=user.coach_profile)
        return AvailabilitySlot.objects.none()

    def perform_create(self, serializer):
        coach, _ = CoachProfile.objects.get_or_create(user=self.request.user)
        serializer.save(coach=coach)


class AppointmentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Appointment.objects.none()

        is_coach = hasattr(user, 'coach_profile')
        scope = self.request.query_params.get('scope', 'all')
        as_coach_param = self.request.query_params.get('as_coach')
        now = timezone.now()

        if as_coach_param == 'true' and is_coach:
            queryset = Appointment.objects.filter(coach=user.coach_profile)
        elif as_coach_param == 'false':
            queryset = Appointment.objects.filter(user=user)
        else:
            # Pour les listes par défaut ou les actions detail (update_status, pastoral_notes)
            if is_coach and self.action in ['update_status', 'pastoral_notes', 'retrieve']:
                queryset = Appointment.objects.filter(Q(user=user) | Q(coach=user.coach_profile))
            else:
                queryset = Appointment.objects.filter(user=user)

        queryset = queryset.select_related('coach__user', 'user')

        if scope == 'upcoming':
            queryset = queryset.filter(appointment_date__gte=now).exclude(status__in=['COMPLETED', 'CANCELLED'])
        elif scope == 'past':
            queryset = queryset.filter(Q(appointment_date__lt=now) | Q(status='COMPLETED'))

        return queryset.order_by('-appointment_date')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, status='PENDING')

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        appointment = self.get_object()
        new_status = request.data.get('status')
        meeting_link = request.data.get('meeting_link')

        if new_status not in ['PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED']:
            return Response({"error": "Statut invalide"}, status=status.HTTP_400_BAD_REQUEST)

        # Autorisation : soit le coach, soit le client pour annuler
        is_coach = hasattr(request.user, 'coach_profile') and appointment.coach == request.user.coach_profile
        is_client = appointment.user == request.user

        if not (is_coach or is_client):
            return Response({"error": "Non autorisé"}, status=status.HTTP_403_FORBIDDEN)

        if new_status in ['CONFIRMED', 'COMPLETED'] and not is_coach:
            return Response({"error": "Seul le coach peut confirmer ou clore la séance"}, status=status.HTTP_403_FORBIDDEN)

        appointment.status = new_status
        if meeting_link:
            appointment.meeting_link = meeting_link
        appointment.save()

        return Response(AppointmentSerializer(appointment).data)

    @action(detail=True, methods=['patch'])
    def pastoral_notes(self, request, pk=None):
        appointment = self.get_object()
        is_coach = hasattr(request.user, 'coach_profile') and appointment.coach == request.user.coach_profile
        if not is_coach:
            return Response({"error": "Seul le coach peut modifier ses notes pastorales"}, status=status.HTTP_403_FORBIDDEN)

        appointment.pastoral_notes = request.data.get('pastoral_notes', '')
        appointment.save()
        return Response({"status": "success", "pastoral_notes": appointment.pastoral_notes})

    @action(detail=False, methods=['get'])
    def coach_stats(self, request):
        user = request.user
        if not hasattr(user, 'coach_profile'):
            return Response({"error": "Profil coach requis"}, status=status.HTTP_400_BAD_REQUEST)

        coach = user.coach_profile
        appts = Appointment.objects.filter(coach=coach)
        now = timezone.now()

        total = appts.count()
        upcoming = appts.filter(appointment_date__gte=now, status__in=['PENDING', 'CONFIRMED']).count()
        completed = appts.filter(status='COMPLETED').count()
        earnings = completed * float(coach.hourly_rate)

        return Response({
            "total_sessions": total,
            "upcoming_sessions": upcoming,
            "completed_sessions": completed,
            "total_earnings_fcfa": earnings,
            "hourly_rate": coach.hourly_rate,
            "rating": coach.rating,
            "reviews_count": coach.reviews_count
        })
