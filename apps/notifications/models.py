from django.db import models
from django.conf import settings

class Notification(models.Model):
    class NotificationType(models.TextChoices):
        ISSUE = 'issue', 'Issue'
        PITCH = 'pitch', 'Pitch'
        PROJECT = 'project', 'Project'
        MENTORSHIP = 'mentorship', 'Mentorship'
        SYSTEM = 'system', 'System'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM
    )
    link_url = models.CharField(max_length=500, blank=True)
    event_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Logical notification identity / event identifier to prevent duplicate notifications (Issue 53)"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] {self.title} -> {self.recipient.email} ({'Read' if self.is_read else 'Unread'})"

    @classmethod
    def send_notification(cls, recipient, title, message, notification_type=NotificationType.SYSTEM, link_url='', event_id=None):
        """
        Sends or deduplicates notification based on (recipient, event_id).
        Guarantees idempotency across webhook/signal triggers.
        """
        if event_id:
            existing = cls.objects.filter(recipient=recipient, event_id=event_id).first()
            if existing:
                return existing, False
        
        instance = cls.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            link_url=link_url,
            event_id=event_id
        )
        return instance, True

