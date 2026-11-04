from django.utils import timezone
def cutoff(now=None):
    now=now or timezone.now()
    try:return now.replace(year=now.year-1)
    except ValueError:return now.replace(year=now.year-1,day=28)
def purge():
    from monitor.models import LogEntry
    from .models import InventorySnapshot,ScanRequest
    boundary=cutoff()
    logs=LogEntry.objects.filter(when__lt=boundary).delete()[0]
    snapshots=InventorySnapshot.objects.filter(completed_at__lt=boundary).delete()[0]
    ScanRequest.objects.filter(created_at__lt=boundary).delete()
    return {'deleted_logs':logs,'deleted_inventory_rows':snapshots}
