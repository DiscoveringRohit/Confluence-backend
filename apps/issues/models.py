from django.db import models
from django.conf import settings
from apps.users.models import University

class Issue(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        VALIDATED = 'validated', 'Validated & Published'
        ADOPTED = 'adopted', 'Adopted by University'
        ASSIGNED = 'assigned', 'Team Assigned'
        RESOLVED = 'resolved', 'Resolved & Tracked'

    class Category(models.TextChoices):
        EDUCATION = 'education', 'Education'
        HEALTHCARE = 'healthcare', 'Healthcare'
        AGRICULTURE = 'agriculture', 'Agriculture'
        WATER = 'water', 'Water & Sanitation'
        ENVIRONMENT = 'environment', 'Environment & Forests'
        ENERGY = 'energy', 'Renewable Energy'
        URBAN_INFRA = 'urban_infra', 'Urban Infrastructure'
        ACCESSIBILITY = 'accessibility', 'Accessibility & Inclusion'
        PUBLIC_ADMIN = 'public_admin', 'Public Administration'
        RURAL_LIVELIHOODS = 'rural_livelihoods', 'Rural Livelihoods'
        OTHER = 'other', 'Other'

    title = models.CharField(max_length=255)
    description = models.TextField(help_text="Detailed description of the problem")
    expected_outcome = models.TextField(help_text="Expected social impact or desired solution")
    
    # Media
    photo = models.ImageField(upload_to='issues/photos/', blank=True, null=True, help_text="Mandatory photographic evidence")
    photo_url = models.URLField(blank=True, help_text="Alternative web link or cloud storage URL")
    documents = models.FileField(upload_to='issues/docs/', blank=True, null=True)

    # Location
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    district = models.CharField(max_length=100, db_index=True)
    address = models.CharField(max_length=255, blank=True)

    # Categorization & AI Triage
    category = models.CharField(max_length=50, choices=Category.choices, default=Category.OTHER, db_index=True)
    ai_confidence = models.FloatField(default=0.0, help_text="Confidence score from AI categorization")
    ai_triage_notes = models.TextField(blank=True)

    # Status & Moderation
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_issues'
    )
    duplicate_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicates',
        help_text="Reference to original issue if marked as duplicate"
    )
    is_escalated = models.BooleanField(default=False, help_text="Auto-escalated if unadopted past window")

    # Citizen resolution feedback loop
    citizen_verified_resolved = models.BooleanField(null=True, blank=True)
    citizen_feedback_on_resolution = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title} ({self.district})"


class Adoption(models.Model):
    class Mode(models.TextChoices):
        SELF_ADOPTED = 'self_adopted', 'University Self-Adopted'
        NOMINATION_APPROVED = 'nomination_approved', 'Student Nomination Approved'

    issue = models.OneToOneField(
        Issue,
        on_delete=models.CASCADE,
        related_name='adoption'
    )
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='adopted_issues'
    )
    mode = models.CharField(max_length=30, choices=Mode.choices, default=Mode.SELF_ADOPTED)
    nominated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nominations_approved',
        help_text="Student who initiated the nomination"
    )
    adopted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.university.name} adopted {self.issue.title}"


class StudentNomination(models.Model):
    """
    Tracks nomination requests sent by students to their university coordinator.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        APPROVED = 'approved', 'Approved (Adoption Created)'
        REJECTED = 'rejected', 'Rejected'

    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name='student_nominations'
    )
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='received_nominations'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_nominations'
    )
    rationale = models.TextField(blank=True, help_text="Why the student believes their university should solve this")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('issue', 'university', 'student')

    def __str__(self):
        return f"Nomination: {self.student.name} -> {self.issue.title} ({self.get_status_display()})"
