from rest_framework import serializers
from .models import SMSTemplate, SMSLog


class SMSTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SMSTemplate
        fields = ['id', 'title', 'content', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SMSLogSerializer(serializers.ModelSerializer):
    template_title = serializers.SerializerMethodField()
    sent_by_display = serializers.SerializerMethodField()

    class Meta:
        model = SMSLog
        fields = [
            'id', 'template_title', 'sent_by_display',
            'recipient_civilite', 'recipient_name',
            'to_hash', 'status', 'credits_used', 'sent_at', 'error_message', 'motif',
        ]
        read_only_fields = fields

    def get_template_title(self, obj):
        return obj.template.title if obj.template else 'Message libre'

    def get_sent_by_display(self, obj):
        return obj.sent_by.nom_officine if obj.sent_by else 'Inconnu'


class SMSPreviewSerializer(serializers.Serializer):
    template_id = serializers.IntegerField(required=False)
    content = serializers.CharField(required=False)
    custom_vars = serializers.DictField(required=False, default=dict)

    def validate(self, data):
        if not data.get('template_id') and not data.get('content'):
            raise serializers.ValidationError(
                "Fournir template_id ou content."
            )
        return data


class SMSSendSerializer(serializers.Serializer):
    to = serializers.CharField()
    message = serializers.CharField()
    template_id = serializers.IntegerField(required=False)
    recipient_civilite = serializers.CharField(max_length=3, required=False, default='')
    recipient_name = serializers.CharField(max_length=200, required=False, default='')
    motif = serializers.CharField(max_length=255, required=False, default='')

