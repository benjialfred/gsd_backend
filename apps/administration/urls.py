from django.urls import path
from .views import KYCQueueView, KYCReviewView

urlpatterns = [
    path('kyc/queue/', KYCQueueView.as_view(), name='admin-kyc-queue'),
    path('kyc/review/<int:pk>/', KYCReviewView.as_view(), name='admin-kyc-review'),
]
