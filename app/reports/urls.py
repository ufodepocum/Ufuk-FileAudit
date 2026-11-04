from django.urls import path
from . import views
app_name='reports'
urlpatterns=[path('logs/',views.logs,name='logs'),path('grafikler/',views.graphs,name='graphs'),path('grafikler/tara/',views.request_scan,name='scan'),path('monitor/api/inventory/',views.inventory_ingest),path('monitor/api/scan/',views.scan_poll),path('monitor/api/scan/ack/',views.scan_ack)]
