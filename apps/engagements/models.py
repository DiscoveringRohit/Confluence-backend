from django.db import models
from django.conf import settings
from apps.issues.models import Issue
from apps.pitches.models import Pitch
from apps.users.models import Organization

class IndustryEngagement(models.Model):
    class EngagementType(models.TextChoices):
        MENTORSHIP = 'mentorship', 'Mentorship & Advisory'
        FUNDING = 'funding', 'CSR / Grant Funding'
        PROTOTYPING = 'prototyping', 'Prototyping & Lab Access'
        TECHNOLOGY_TRANSFER = 'technology_transfer', 'Technology Transfer & Licensing'

    class Initiator(models.TextChoices):
        UNIVERSITY = 'university', 'University'
        INDUSTRY = 'industry', 'Industry Partner'

    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        ACCEPTED = 'accepted', 'Accepted & MOU Initiated'
        ACTIVE = 'active', 'Active Collaboration'
        COMPLETED = 'completed', 'Completed'
        DECLINED = 'declined', 'Declined'

    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name='industry_engagements'
    )
    pitch = models.ForeignKey(
        Pitch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='industry_engagements',
        help_text="Assigned pitch/solution this partnership attaches to"
    )
    industry_org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='engagements'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_engagements'
    )
    engagement_type = models.CharField(
        max_length=40,
        choices=EngagementType.choices,
        default=EngagementType.MENTORSHIP
    )
    initiator = models.CharField(
        max_length=20,
        choices=Initiator.choices
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED
    )
    proposal_notes = models.TextField(help_text="Scope of mentorship, funding amount, or prototyping support offered/sought")
    response_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.industry_org.name} <-> Issue #{self.issue_id} ({self.get_status_display()})"
