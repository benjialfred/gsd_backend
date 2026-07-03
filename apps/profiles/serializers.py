from rest_framework import serializers
from .models import ProfileMedia, KYCSubmission

class ProfileMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileMedia
        fields = ['id', 'media_type', 'file', 'is_primary', 'display_order', 'is_verified_media', 'moderation_status', 'created_at']
        read_only_fields = ['is_verified_media', 'moderation_status', 'created_at']

class KYCSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCSubmission
        fields = ['status', 'id_document_front', 'id_document_back', 'selfie_video', 'submitted_at']
        read_only_fields = ['status', 'submitted_at']
