from rest_framework import serializers
from .models import LogEntry
class LogEntrySerializer(serializers.ModelSerializer):
    def validate_when(self, value):
        from reports.retention import cutoff
        from django.utils import timezone
        from datetime import timedelta
        if value < cutoff():
            raise serializers.ValidationError('Bir yıldan eski kayıt kabul edilmez.')
        if value > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError('Gelecek tarihli kayıt kabul edilmez.')
        return value

    class Meta:
        model=LogEntry
        fields=['id','when','who','action','what','where','share_name','object_type','host','status','old_path','new_path','old_owner','new_owner','old_acl','new_acl']
