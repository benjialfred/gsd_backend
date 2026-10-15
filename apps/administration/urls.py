from django.urls import path
from .views import (
    AdminMetricsView,
    AdminUsersListView,
    AdminUserDetailView,
    AdminTransactionsListView,
    AdminEventsListView,
    AdminEventDetailView,
    AdminRegistrationsListView,
    AdminCheckInView,
    AdminCoachesListView,
    AdminAuditLogsView,
    KYCQueueView,
    KYCReviewView
)

urlpatterns = [
    # Métriques exécutives globales
    path('metrics/', AdminMetricsView.as_view(), name='admin-metrics'),

    # Gestion & Modération des Utilisateurs
    path('users/', AdminUsersListView.as_view(), name='admin-users-list'),
    path('users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),

    # Audit Financier & Transactions NelsiusPay
    path('transactions/', AdminTransactionsListView.as_view(), name='admin-transactions-list'),

    # Événements & Billetterie
    path('events/', AdminEventsListView.as_view(), name='admin-events-list'),
    path('events/<int:pk>/', AdminEventDetailView.as_view(), name='admin-event-detail'),
    path('registrations/', AdminRegistrationsListView.as_view(), name='admin-registrations-list'),
    path('registrations/check-in/', AdminCheckInView.as_view(), name='admin-check-in'),

    # Conseillers & Coaching
    path('coaches/', AdminCoachesListView.as_view(), name='admin-coaches-list'),

    # KYC Compliance Queue & Validation
    path('kyc/queue/', KYCQueueView.as_view(), name='admin-kyc-queue'),
    path('kyc/review/<int:pk>/', KYCReviewView.as_view(), name='admin-kyc-review'),

    # Journal d'audit
    path('audit-logs/', AdminAuditLogsView.as_view(), name='admin-audit-logs'),
]
