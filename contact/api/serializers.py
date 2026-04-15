"""Contact API Serializers"""
from rest_framework import serializers
from contact.models import ContactOption


class ContactOptionSerializer(serializers.ModelSerializer):
    """Serializer para ContactOption (crear contacto vía API)"""
    
    class Meta:
        model = ContactOption
        fields = ['id', 'name', 'email', 'contact_method', 'subject', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']
