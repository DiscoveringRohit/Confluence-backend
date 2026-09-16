from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from apps.issues.models import Issue, StudentNomination
from apps.pitches.models import Pitch, CommunityFeedback, Project, ProjectMilestone
from apps.engagements.models import IndustryEngagement
from .models import Notification

User = get_user_model()


@receiver(post_save, sender=Issue)
def handle_issue_notification(sender, instance, created, **kwargs):
    if created:
        if instance.submitted_by:
            Notification.send_notification(
                recipient=instance.submitted_by,
                title="Civic Problem Submitted",
                message=f"Your issue '{instance.title}' was received and scheduled for AI triage.",
                notification_type=Notification.NotificationType.ISSUE,
                link_url=f"/issues/{instance.id}/",
                event_id=f"issue_{instance.id}_created"
            )
    else:
        if instance.submitted_by:
            if instance.status == Issue.Status.VALIDATED:
                Notification.send_notification(
                    recipient=instance.submitted_by,
                    title="Issue Validated by District",
                    message=f"'{instance.title}' has been validated and placed into the open university pipeline.",
                    notification_type=Notification.NotificationType.ISSUE,
                    link_url=f"/issues/{instance.id}/",
                    event_id=f"issue_{instance.id}_validated"
                )
            elif instance.status == Issue.Status.ADOPTED:
                Notification.send_notification(
                    recipient=instance.submitted_by,
                    title="Problem Adopted by University",
                    message=f"'{instance.title}' has been adopted by an engineering university for technical prototyping.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/issues/{instance.id}/",
                    event_id=f"issue_{instance.id}_adopted"
                )
            elif instance.status == Issue.Status.RESOLVED:
                Notification.send_notification(
                    recipient=instance.submitted_by,
                    title="Field Deployment Completed",
                    message=f"'{instance.title}' has completed field deployment. Please verify and confirm resolution.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/issues/{instance.id}/",
                    event_id=f"issue_{instance.id}_resolved"
                )


@receiver(post_save, sender=StudentNomination)
def handle_nomination_notification(sender, instance, created, **kwargs):
    if not created and instance.student:
        if instance.status == StudentNomination.Status.APPROVED:
            Notification.send_notification(
                recipient=instance.student,
                title="Challenge Nomination Approved! 🎓",
                message=f"Your nomination for '{instance.issue.title}' was approved by the University Coordinator.",
                notification_type=Notification.NotificationType.PROJECT,
                link_url=f"/university/challenges/{instance.issue_id}",
                event_id=f"nomination_{instance.id}_approved"
            )
        elif instance.status == StudentNomination.Status.REJECTED:
            Notification.send_notification(
                recipient=instance.student,
                title="Nomination Review Concluded",
                message=f"Your nomination for '{instance.issue.title}' was reviewed and not accepted at this time.",
                notification_type=Notification.NotificationType.ISSUE,
                link_url=f"/issues/{instance.issue_id}/",
                event_id=f"nomination_{instance.id}_rejected"
            )


@receiver(post_save, sender=Pitch)
def handle_pitch_notification(sender, instance, created, **kwargs):
    if created:
        # Notify maintaining university coordinators when pitch submitted
        if instance.university:
            coords = User.objects.filter(university=instance.university, role='university_coordinator')
            for coord in coords:
                Notification.send_notification(
                    recipient=coord,
                    title="New Solution Proposal Submitted",
                    message=f"A new student solution '{instance.title}' was submitted for challenge #{instance.issue_id}.",
                    notification_type=Notification.NotificationType.PITCH,
                    link_url=f"/pitches/{instance.id}/",
                    event_id=f"pitch_{instance.id}_submitted_{coord.id}"
                )
    else:
        # Status transitions
        if instance.status == Pitch.Status.SELECTED:
            for member in instance.student_team.all():
                Notification.send_notification(
                    recipient=member,
                    title="Winning Pitch Selected! 🎉",
                    message=f"Your solution '{instance.title}' was selected by the University Review Board.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/pitches/{instance.id}/",
                    event_id=f"pitch_{instance.id}_selected_{member.id}"
                )
        elif instance.status == Pitch.Status.REJECTED:
            for member in instance.student_team.all():
                Notification.send_notification(
                    recipient=member,
                    title="Pitch Review Complete",
                    message=f"Your pitch '{instance.title}' evaluation has been concluded. Feedback archived in vault.",
                    notification_type=Notification.NotificationType.PITCH,
                    link_url=f"/pitches/{instance.id}/",
                    event_id=f"pitch_{instance.id}_rejected_{member.id}"
                )
        elif instance.status == Pitch.Status.CHANGES_REQUESTED:
            for member in instance.student_team.all():
                Notification.send_notification(
                    recipient=member,
                    title="Changes Requested on Proposal",
                    message=f"Reviewers requested revisions on '{instance.title}'. Please address the review scorecard.",
                    notification_type=Notification.NotificationType.PITCH,
                    link_url=f"/pitches/{instance.id}/",
                    event_id=f"pitch_{instance.id}_changes_{member.id}_v{instance.version}"
                )
        elif instance.status == Pitch.Status.RESUBMITTED:
            if instance.assigned_mentor:
                Notification.send_notification(
                    recipient=instance.assigned_mentor,
                    title="Proposal Resubmitted with Revisions",
                    message=f"Student team has resubmitted revised solution '{instance.title}' (v{instance.version}).",
                    notification_type=Notification.NotificationType.PITCH,
                    link_url=f"/pitches/{instance.id}/",
                    event_id=f"pitch_{instance.id}_resubmitted_mentor_v{instance.version}"
                )

        # Faculty mentor assignment
        if instance.assigned_mentor:
            Notification.send_notification(
                recipient=instance.assigned_mentor,
                title="Assigned as Faculty Mentor",
                message=f"You have been assigned as faculty mentor for student solution '{instance.title}'.",
                notification_type=Notification.NotificationType.MENTORSHIP,
                link_url=f"/pitches/{instance.id}/",
                event_id=f"pitch_{instance.id}_mentor_{instance.assigned_mentor_id}"
            )


@receiver(post_save, sender=Project)
def handle_project_notification(sender, instance, created, **kwargs):
    if not created:
        if instance.status in [Project.Status.PILOT, Project.Status.PROTOTYPE]:
            for member in instance.team.all():
                Notification.send_notification(
                    recipient=member,
                    title="Project Field Phase Started",
                    message=f"Project '{instance.title}' has advanced to {instance.get_status_display()}.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/projects/{instance.id}",
                    event_id=f"project_{instance.id}_{instance.status}_{member.id}"
                )
        elif instance.status == Project.Status.DEPLOYED:
            for member in instance.team.all():
                Notification.send_notification(
                    recipient=member,
                    title="Field Deployment Completed! 🚀",
                    message=f"Deployment evidence recorded for '{instance.title}'. Awaiting citizen verification.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/projects/{instance.id}",
                    event_id=f"project_{instance.id}_deployed_{member.id}"
                )
            if instance.challenge and instance.challenge.submitted_by:
                Notification.send_notification(
                    recipient=instance.challenge.submitted_by,
                    title="Solution Deployed in Field — Verification Requested",
                    message=f"A solution for problem #{instance.challenge_id} has been deployed. Please inspect and confirm resolution.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/issues/{instance.challenge_id}/",
                    event_id=f"project_{instance.id}_citizen_verify_{instance.challenge.submitted_by_id}"
                )
        elif instance.status == Project.Status.VERIFIED:
            for member in instance.team.all():
                Notification.send_notification(
                    recipient=member,
                    title="Citizen Verification Confirmed 🎉",
                    message=f"Citizen confirmed resolution for '{instance.title}'. Eligible for verified outcome certification!",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/projects/{instance.id}",
                    event_id=f"project_{instance.id}_verified_{member.id}"
                )
        elif instance.status == Project.Status.REOPENED:
            for member in instance.team.all():
                Notification.send_notification(
                    recipient=member,
                    title="Verification Incomplete — Challenge Reopened",
                    message=f"Citizen feedback requires further revisions on '{instance.title}'.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/projects/{instance.id}",
                    event_id=f"project_{instance.id}_reopened_{member.id}"
                )


@receiver(post_save, sender=ProjectMilestone)
def handle_milestone_notification(sender, instance, created, **kwargs):
    if created:
        for member in instance.project.team.all():
            Notification.send_notification(
                recipient=member,
                title="New Implementation Milestone Assigned",
                message=f"Milestone '{instance.title}' has been added to project #{instance.project_id}.",
                notification_type=Notification.NotificationType.PROJECT,
                link_url=f"/projects/{instance.project_id}",
                event_id=f"milestone_{instance.id}_created_{member.id}"
            )
    else:
        if instance.status == ProjectMilestone.Status.SUBMITTED and instance.project.mentor:
            Notification.send_notification(
                recipient=instance.project.mentor,
                title="Milestone Deliverables Submitted",
                message=f"Team submitted deliverables for milestone '{instance.title}' (Project #{instance.project_id}).",
                notification_type=Notification.NotificationType.PROJECT,
                link_url=f"/projects/{instance.project_id}",
                event_id=f"milestone_{instance.id}_submitted_{instance.project.mentor_id}"
            )
        elif instance.status == ProjectMilestone.Status.APPROVED:
            for member in instance.project.team.all():
                Notification.send_notification(
                    recipient=member,
                    title="Milestone Approved by Mentor ✅",
                    message=f"Deliverables for '{instance.title}' were approved.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url=f"/projects/{instance.project_id}",
                    event_id=f"milestone_{instance.id}_approved_{member.id}"
                )


@receiver(post_save, sender=CommunityFeedback)
def handle_feedback_score_notification(sender, instance, created, **kwargs):
    if not created and instance.relevance_score is not None:
        if instance.citizen:
            Notification.send_notification(
                recipient=instance.citizen,
                title="Feedback Evaluated by Mentor",
                message=f"Your feedback on Pitch #{instance.pitch_id} was reviewed and received relevance score {instance.relevance_score}/10.",
                notification_type=Notification.NotificationType.PITCH,
                link_url=f"/pitches/{instance.pitch_id}/",
                event_id=f"feedback_{instance.id}_score"
            )


@receiver(post_save, sender=IndustryEngagement)
def handle_engagement_notification(sender, instance, created, **kwargs):
    if not created and instance.created_by:
        if instance.status == IndustryEngagement.Status.ACCEPTED:
            Notification.send_notification(
                recipient=instance.created_by,
                title="CSR Partnership Accepted",
                message=f"Your engagement proposal for issue #{instance.issue_id} has been accepted.",
                notification_type=Notification.NotificationType.PROJECT,
                link_url="/engagements/",
                event_id=f"engagement_{instance.id}_accepted"
            )
        elif instance.status == IndustryEngagement.Status.ACTIVE:
            Notification.send_notification(
                recipient=instance.created_by,
                title="CSR Partnership Activated",
                message=f"Your engagement for issue #{instance.issue_id} is now active.",
                notification_type=Notification.NotificationType.PROJECT,
                link_url="/engagements/",
                event_id=f"engagement_{instance.id}_active"
            )
