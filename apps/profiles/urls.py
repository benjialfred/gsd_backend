from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProfileCompletionView, ProfileMediaViewSet, KYCSubmissionView, ReferenceDataView, KYCAdminViewSet

router = DefaultRouter()
router.register('media', ProfileMediaViewSet, basename='profile-media')
router.register('admin/kyc', KYCAdminViewSet, basename='admin-kyc')

urlpatterns = [
    path('reference-data/', ReferenceDataView.as_view(), name='reference-data'),
    path('me/completion/', ProfileCompletionView.as_view(), name='profile-completion'),
    path('me/kyc/', KYCSubmissionView.as_view(), name='profile-kyc'),
    path('me/', include(router.urls)),
]
