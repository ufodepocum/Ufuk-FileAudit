from django.db import models
from django.conf import settings

class InitialAccount(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    must_change=models.BooleanField(default=True)
    initial_hash=models.CharField(max_length=256)

class InventorySnapshot(models.Model):
    scan_id=models.UUIDField(unique=True)
    started_at=models.DateTimeField(db_index=True)
    completed_at=models.DateTimeField(db_index=True)
    host=models.GenericIPAddressField()
    errors=models.PositiveBigIntegerField(default=0)
    files=models.PositiveBigIntegerField(default=0)
    skipped=models.PositiveBigIntegerField(default=0)
    class Meta: ordering=['-completed_at']

class OwnerUsage(models.Model):
    snapshot=models.ForeignKey(InventorySnapshot,on_delete=models.CASCADE,related_name='owners')
    owner=models.CharField(max_length=256)
    share=models.CharField(max_length=100)
    files=models.PositiveBigIntegerField(default=0)
    logical_bytes=models.PositiveBigIntegerField(default=0)
    allocated_bytes=models.PositiveBigIntegerField(default=0)
    allocation_errors=models.PositiveBigIntegerField(default=0)
    class Meta:
        indexes=[models.Index(fields=['snapshot','share'])]

class ScanRequest(models.Model):
    created_at=models.DateTimeField(auto_now_add=True)
    requested_by=models.CharField(max_length=200)
    acknowledged_at=models.DateTimeField(null=True,blank=True)
