from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.issues.models import Issue
from apps.notifications.models import Notification

User = get_user_model()

class NotificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.citizen = User.objects.create_user(
            email='citizen_test@confluence.in',
            password='testpassword123',
            name='Test Citizen',
            role='citizen'
        )
        self.client.force_authenticate(user=self.citizen)

    def test_notification_creation_on_issue(self):
        # Submitting an issue should automatically trigger signal to create a notification
        issue = Issue.objects.create(
            submitted_by=self.citizen,
            title='Water Contamination Test',
            description='Test description for water issue',
            category='water',
            district='Ranchi'
        )

        notif = Notification.objects.filter(recipient=self.citizen).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.notification_type, Notification.NotificationType.ISSUE)
        self.assertIn('Water Contamination Test', notif.message)
        self.assertFalse(notif.is_read)

    def test_notification_list_and_mark_read(self):
        notif = Notification.objects.create(
            recipient=self.citizen,
            title='Test Notification',
            message='Test message content',
            notification_type=Notification.NotificationType.SYSTEM
        )

        res = self.client.get('/api/notifications/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data if isinstance(res.data, list) else res.data.get('results', [])
        self.assertTrue(len(data) >= 1)

        # Mark single as read
        res_read = self.client.post(f'/api/notifications/{notif.id}/read/')
        self.assertEqual(res_read.status_code, status.HTTP_200_OK)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

        # Mark all as read
        res_all = self.client.post('/api/notifications/mark-all-read/')
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
