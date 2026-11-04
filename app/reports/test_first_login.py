from django.test import TestCase
from django.contrib.auth.models import User
from .models import InitialAccount
class FirstLoginTests(TestCase):
    def test_default_account_requires_password_change_and_unlocks_after_change(self):
        user=User.objects.create_user('admin',password='admin',is_staff=True,is_superuser=True)
        state=InitialAccount.objects.create(user=user,initial_hash=user.password,must_change=True)
        self.client.login(username='admin',password='admin')
        self.assertRedirects(self.client.get('/grafikler/'),'/admin/password_change/',fetch_redirect_response=False)
        r=self.client.post('/admin/password_change/',{'old_password':'admin','new_password1':'NewPass-for-tests-123','new_password2':'NewPass-for-tests-123'})
        self.assertEqual(r.status_code,302)
        self.assertEqual(self.client.get('/grafikler/').status_code,200)
        state.refresh_from_db();self.assertFalse(state.must_change)
    def test_bootstrap_does_not_reset_existing_password(self):
        from unittest.mock import patch
        import bootstrap
        with patch.dict('os.environ',{'FILESERVER_IP':'192.0.2.10'}):
            bootstrap.initialize()
            user=User.objects.get(username='admin');self.assertTrue(user.check_password('admin'))
            user.set_password('OwnerAlreadyChanged123');user.save();bootstrap.initialize();user.refresh_from_db()
            self.assertTrue(user.check_password('OwnerAlreadyChanged123'))
