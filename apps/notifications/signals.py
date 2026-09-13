from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from apps.issues.models import Issue
from apps.pitches.models import Pitch, CommunityFeedback
from apps.engagements.models import IndustryEngagement
from .models import Notification

User = get_user_model()

@receiver(post_save, sender=Issue)
def handle_issue_notification(sender, instance, created, **kwargs):
    if created:
        if instance.submitted_by:
            Notification.objects.create(
                recipient=instance.submitted_by,
                title="Civic Problem Submitted",
                message=f"Your issue '{instance.title}' was received and scheduled for AI triage.",
                notification_type=Notification.NotificationType.ISSUE,
                link_url=f"/issues/{instance.id}/"
            )
    else:
        if instance.submitted_by:
            if instance.status == Issue.Status.VALIDATED:
                Notification.objects.get_or_create(
                    recipient=instance.submitted_by,
                    title="Issue Validated by District",
                    message=f"'{instance.title}' has been validated and placed into the open university pipeline.",
                    notification_type=Notification.NotificationType.ISSUE,
                    link_url=f"/issues/{instance.id}/"
                )
            elif instance.status == Issue.Status.ADOPTED:
                Notification.objects.get_or_create(
                    recipient=instance.submitted_by,
                    title="Problem Adopted by University",
                    message=f"'{instance.title}' has been adopted by an engineering university for technical prototyping.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/issues/{instance.id}/"
                )
            elif instance.status == Issue.Status.RESOLVED:
                Notification.objects.get_or_create(
                    recipient=instance.submitted_by,
                    title="Field Deployment Completed",
                    message=f"'{instance.title}' has completed field deployment. Please verify and confirm resolution.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/issues/{instance.id}/"
                )


@receiver(post_save, sender=Pitch)
def handle_pitch_notification(sender, instance, created, **kwargs):
    if not created:
        # Notify team when pitch status changes
        if instance.status == Pitch.Status.SELECTED:
            for member in instance.student_team.all():
                Notification.objects.get_or_create(
                    recipient=member,
                    title="Winning Pitch Selected! 🎉",
                    message=f"Your solution '{instance.title}' was selected by the University Review Board.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/pitches/{instance.id}/"
                )
        elif instance.status == Pitch.Status.REJECTED:
            for member in instance.student_team.all():
                Notification.objects.get_or_create(
                    recipient=member,
                    title="Pitch Review Complete",
                    message=f"Your pitch '{instance.title}' evaluation has been concluded. Feedback archived in vault.",
                    notification_type=Notification.NotificationType.PITCH,
                    link_url=f"/pitches/{instance.id}/"
                )

        # Notify mentor when assigned
        if instance.assigned_mentor:
            Notification.objects.get_or_create(
                recipient=instance.assigned_mentor,
                title="Assigned as Faculty Mentor",
                message=f"You have been assigned as faculty mentor for student solution '{instance.title}'.",
                notification_type=Notification.NotificationType.MENTORSHIP,
                link_url=f"/pitches/{instance.id}/"
            )


@receiver(post_save, sender=CommunityFeedback)
def handle_feedback_score_notification(sender, instance, created, **kwargs):
    if not created and instance.relevance_score is not None:
        if instance.citizen:
            Notification.objects.get_or_create(
                recipient=instance.citizen,
                title="Feedback Evaluated by Mentor",
                message=f"Your feedback on Pitch #{instance.pitch_id} was reviewed and received relevance score {instance.relevance_score}/10.",
                notification_type=Notification.NotificationType.PITCH,
                link_url=f"/pitches/{instance.pitch_id}/"
            )


@receiver(post_save, sender=IndustryEngagement)
def handle_engagement_notification(sender, instance, created, **kwargs):
    if not created and instance.created_by:
        if instance.status == IndustryEngagement.Status.ACCEPTED:
            Notification.objects.get_or_create(
                recipient=instance.created_by,
                title="CSR Partnership Accepted",
                message=f"Your engagement proposal for issue #{instance.issue_id} has been accepted.",
                notification_type=Notification.NotificationType.PROJECT,
                link_url="/engagements/"
            )
        elif instance.status == IndustryEngagement.Status.ACTIVE:
            Notification.objects.get_or_create(
                recipient=instance.created_by,
                title="CSR Partnership Activated",
                message=f"Your engagement for issue #{instance.issue_id} is now active.",
                notification_type=Notification.NotificationType.PROJECT,
                link_url="/engagements/"
            )
