from rest_framework import serializers
from .models import PaymentTransaction


class PaymentTransactionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    purpose_display = serializers.CharField(source='get_purpose_display', read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'reference', 'nelsius_transaction_id', 'amount', 
            'currency', 'payment_method', 'purpose', 'purpose_display', 
            'related_id', 'status', 'status_display', 'checkout_url', 
            'customer_name', 'customer_email', 'customer_phone', 
            'payment_metadata', 'paid_at', 'created_at'
        ]
        read_only_fields = ['reference', 'nelsius_transaction_id', 'status', 'paid_at', 'created_at']
