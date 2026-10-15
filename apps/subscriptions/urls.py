from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubscriptionPlanViewSet, UserSubscriptionViewSet

router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet, basename='subscription-plan')
router.register(r'user', UserSubscriptionViewSet, basename='user-subscription')

urlpatterns = [
    path('', include(router.urls)),
]
