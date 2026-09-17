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

    EngagementType.CSR_SPONSORSHIP = EngagementType.FUNDING
    EngagementType.INCUBATION = EngagementType.PROTOTYPING

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
    project = models.ForeignKey(
        'pitches.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='industry_engagements',
        help_text="Active implementation project this partnership supports"
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


class Funding(models.Model):
    class FundingType(models.TextChoices):
        CSR_GRANT = 'csr_grant', 'CSR Grant'
        GOVT_SCHEME = 'govt_scheme', 'Government Innovation Scheme'
        EQUITY = 'equity', 'Incubation Equity / Seed'
        PRIZE = 'prize', 'Competition / Hackathon Prize'

    class Status(models.TextChoices):
        PROPOSED = 'proposed', 'Funding Proposed'
        APPROVED = 'approved', 'Approved'
        DISBURSED = 'disbursed', 'Disbursed'
        CANCELLED = 'cancelled', 'Cancelled'

    project = models.ForeignKey('pitches.Project', on_delete=models.CASCADE, related_name='funding_grants')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='funding_grants')
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Funding amount in INR")
    funding_type = models.CharField(max_length=30, choices=FundingType.choices, default=FundingType.CSR_GRANT)
    purpose = models.TextField(blank=True, help_text="Purpose of grant / funding terms")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED)
    approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Funding ₹{self.amount} by {self.organization.name} -> Project #{self.project_id} [{self.get_status_display()}]"

