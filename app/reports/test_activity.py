from datetime import timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from monitor.models import LogEntry

class ActivityHistoryTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user('reader',password='test-password'))
        self.now=timezone.localtime().replace(hour=12,minute=0,second=0,microsecond=0)
        for who,action,minutes in [('DEMO\\anna','Accessed',0),('DEMO\\anna','Removed',1),('DEMO\\annabelle','Created',2)]:
            LogEntry.objects.create(when=self.now-timedelta(minutes=minutes),who=who,action=action,what='Subfolder\\report.txt',share_name='\\\\fs-demo\\Veri',where='fs-demo',object_type='File',host='192.0.2.5',status='Success')
    def test_exact_actor_and_full_day_show_ordered_activity_with_full_path(self):
        day=self.now.strftime('%Y-%m-%d');params={'actor':'DEMO\\anna','start_date':day,'end_date':day}
        r=self.client.get('/logs/',params)
        self.assertEqual(r.status_code,200);self.assertEqual(r.context['total'],2)
        self.assertEqual([e.action for e in r.context['page_obj']],['Accessed','Removed'])
        self.assertContains(r,'\\\\fs-demo\\Veri\\Subfolder\\report.txt')
        self.assertContains(r,'İşlemi yapan kullanıcı');self.assertEqual(len(r.context['filter_form'].fields['actor'].choices),3)
        csv=self.client.get('/logs/',params|{'export':'csv'}).content.decode('utf-8-sig')
        self.assertIn('DEMO\\anna',csv);self.assertNotIn('annabelle',csv)
        self.assertIn('\\\\fs-demo\\Veri\\Subfolder\\report.txt',csv)
    def test_empty_range_does_not_invent_events_and_offers_last_real_event_day(self):
        day=(self.now-timedelta(days=2)).strftime('%Y-%m-%d')
        r=self.client.get('/logs/',{'actor':'DEMO\\anna','start_date':day,'end_date':day})
        self.assertEqual(r.context['total'],0);self.assertEqual(r.context['actor_last_seen'],self.now)
        self.assertContains(r,'Son işlem gününü aç')
    def test_explicit_action_filter_and_substring_compatibility(self):
        day=self.now.strftime('%Y-%m-%d')
        r=self.client.get('/logs/',{'actor':'DEMO\\anna','action':'Removed','start_date':day,'end_date':day})
        self.assertEqual(r.context['total'],1)
        r=self.client.get('/logs/',{'who':'anna','start_date':day,'end_date':day})
        self.assertEqual(r.context['total'],3)
