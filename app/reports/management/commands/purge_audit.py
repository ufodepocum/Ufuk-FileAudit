from django.core.management.base import BaseCommand
from reports.retention import purge
class Command(BaseCommand):
    help='Bir takvim yılından eski kayıt ve envanter ölçümlerini temizler.'
    def handle(self,*args,**kwargs):self.stdout.write(str(purge()))
