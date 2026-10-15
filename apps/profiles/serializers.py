from rest_framework import serializers
from .models import ProfileMedia, KYCSubmission

class ProfileMediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProfileMedia
        fields = ['id', 'media_type', 'file', 'url', 'is_primary', 'display_order', 'is_verified_media', 'moderation_status', 'created_at']
        read_only_fields = ['is_verified_media', 'moderation_status', 'created_at']

    def get_url(self, obj):
        if not obj.file:
            return None
        url = obj.file.url
        request = self.context.get('request')
        if request and not url.startswith(('http://', 'https://')):
            return request.build_absolute_uri(url)
        return url

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        resolved_url = self.get_url(instance)
        if resolved_url:
            ret['url'] = resolved_url
            ret['file'] = resolved_url
        return ret


class KYCSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCSubmission
        fields = ['status', 'id_document_front', 'id_document_back', 'selfie_video', 'submitted_at']
        read_only_fields = ['status', 'submitted_at']
