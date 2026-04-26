from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ResourceViewSet, TransactionViewSet

router = DefaultRouter()
router.register('resources', ResourceViewSet)
router.register('transactions', TransactionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
