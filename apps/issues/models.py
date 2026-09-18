from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.users.models import University

class Issue(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        VALIDATING = 'validating', 'Under Moderation'
        VALIDATED = 'validated', 'Validated & Published'
        AVAILABLE_FOR_ADOPTION = 'available_for_adoption', 'Available for Adoption'
        ADOPTION_REQUESTED = 'adoption_requested', 'Adoption Requested'
        REJECTED = 'rejected', 'Rejected'
        DUPLICATE = 'duplicate', 'Duplicate'
        ADOPTED = 'adopted', 'Adopted by University'
        OPEN = 'open', 'Open for Solutions'
        UNDER_REVIEW = 'under_review', 'Solutions Under Review'
        SOLUTION_SELECTED = 'solution_selected', 'Solution Selected'
        ASSIGNED = 'assigned', 'Team Assigned'
        PROJECT = 'project', 'Implementation Project Active'
        PROTOTYPE = 'prototype', 'Prototype in Development'
        PILOT = 'pilot', 'Pilot Testing in Field'
        DEPLOYED = 'deployed', 'Deployed in Field'
        AWAITING_CITIZEN_VERIFICATION = 'awaiting_citizen_verification', 'Awaiting Citizen Verification'
        AWAITING_VERIFICATION = 'awaiting_verification', 'Awaiting Citizen Verification (Alias)'
        VERIFIED = 'verified', 'Verified by Citizen'
        FAILED = 'failed', 'Verification Failed'
        RESOLVED = 'resolved', 'Resolved & Tracked'
        REOPENED = 'reopened', 'Reopened'

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

    public_id = models.CharField(max_length=50, blank=True, null=True, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(help_text="Detailed description of the problem")
    context = models.TextField(blank=True, help_text="Background context for the challenge")
    expected_outcome = models.TextField(help_text="Expected social impact or desired solution")
    requirements = models.TextField(blank=True, help_text="Functional and domain requirements")
    constraints = models.TextField(blank=True, help_text="Technical, legal, operational or geographic constraints")
    acceptance_criteria = models.TextField(blank=True, help_text="Requirements, target metrics, and acceptance criteria")
    
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

    # Issue 42: Explicit Challenge Ownership Model
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validated_issues',
        help_text="Authority/moderator who validated and approved this challenge"
    )
    maintaining_university = models.ForeignKey(
        'users.University',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintained_issues',
        help_text="University currently maintaining this challenge repository"
    )
    managed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_issues',
        help_text="University coordinator who actively manages this repository"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def ownership(self):
        """Authoritative ownership model (Section 42)."""
        creator = {
            'id': self.submitted_by_id,
            'name': getattr(self.submitted_by, 'name', '') or self.submitted_by.email,
            'role': 'citizen'
        } if self.submitted_by else None

        validator = {
            'id': self.validated_by_id,
            'name': getattr(self.validated_by, 'name', '') or self.validated_by.email,
            'role': 'authority'
        } if self.validated_by else None

        univ = None
        if self.maintaining_university:
            univ = {
                'id': self.maintaining_university_id,
                'name': self.maintaining_university.name,
                'code': getattr(self.maintaining_university, 'code', '')
            }
        elif hasattr(self, 'adoption') and self.adoption and self.adoption.university:
            univ = {
                'id': self.adoption.university_id,
                'name': self.adoption.university.name,
                'code': getattr(self.adoption.university, 'code', '')
            }

        mgr = None
        if self.managed_by:
            mgr = {
                'id': self.managed_by_id,
                'name': getattr(self.managed_by, 'name', '') or self.managed_by.email,
                'role': 'coordinator'
            }
        elif hasattr(self, 'adoption') and self.adoption and self.adoption.coordinator:
            mgr = {
                'id': self.adoption.coordinator_id,
                'name': getattr(self.adoption.coordinator, 'name', '') or self.adoption.coordinator.email,
                'role': 'coordinator'
            }

        return {
            'created_by': creator,
            'validated_by': validator,
            'maintaining_university': univ,
            'managed_by': mgr,
        }

    @property
    def created_by(self):
        """Specification Section 58 alias to submitted_by."""
        return self.submitted_by

    @property
    def challenge_title(self):
        """Specification Section 58 & 81 alias to title."""
        return self.title

    @property
    def maintainer_university(self):
        """Specification Section 58 alias to maintaining_university."""
        return self.maintaining_university

    @property
    def location(self):
        """Specification Section 58 structured location dictionary."""
        return {
            'latitude': float(self.latitude) if self.latitude is not None else None,
            'longitude': float(self.longitude) if self.longitude is not None else None,
            'district': self.district,
            'address': self.address,
        }

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.public_id and self.id:
            self.public_id = f"CH-{self.id:05d}"
            super().save(update_fields=['public_id'])

    def transition_status(self, new_status, actor=None, reason=''):
        prev_status = self.status
        if prev_status == new_status:
            return None

        VALID_TRANSITIONS = {
            self.Status.SUBMITTED: [self.Status.VALIDATING, self.Status.VALIDATED, self.Status.REJECTED, self.Status.DUPLICATE],
            self.Status.VALIDATING: [self.Status.VALIDATED, self.Status.REJECTED, self.Status.DUPLICATE],
            self.Status.VALIDATED: [self.Status.ADOPTED, self.Status.AVAILABLE_FOR_ADOPTION, self.Status.ADOPTION_REQUESTED, self.Status.REJECTED],
            self.Status.AVAILABLE_FOR_ADOPTION: [self.Status.ADOPTED, self.Status.ADOPTION_REQUESTED, self.Status.REJECTED],
            self.Status.ADOPTION_REQUESTED: [self.Status.ADOPTED, self.Status.AVAILABLE_FOR_ADOPTION, self.Status.REJECTED],
            self.Status.ADOPTED: [self.Status.OPEN, self.Status.UNDER_REVIEW, self.Status.SOLUTION_SELECTED, self.Status.ASSIGNED, self.Status.PROJECT, self.Status.PILOT, self.Status.DEPLOYED, self.Status.AWAITING_VERIFICATION, self.Status.AWAITING_CITIZEN_VERIFICATION],
            self.Status.OPEN: [self.Status.UNDER_REVIEW, self.Status.SOLUTION_SELECTED, self.Status.ASSIGNED, self.Status.PROJECT],
            self.Status.UNDER_REVIEW: [self.Status.SOLUTION_SELECTED, self.Status.ASSIGNED, self.Status.OPEN, self.Status.PROJECT],
            self.Status.SOLUTION_SELECTED: [self.Status.ASSIGNED, self.Status.PROJECT, self.Status.PILOT, self.Status.AWAITING_VERIFICATION, self.Status.AWAITING_CITIZEN_VERIFICATION],
            self.Status.ASSIGNED: [self.Status.PROJECT, self.Status.PROTOTYPE, self.Status.PILOT, self.Status.DEPLOYED, self.Status.AWAITING_VERIFICATION, self.Status.AWAITING_CITIZEN_VERIFICATION, self.Status.REOPENED, self.Status.RESOLVED],
            self.Status.PROJECT: [self.Status.PROTOTYPE, self.Status.PILOT, self.Status.DEPLOYED, self.Status.AWAITING_VERIFICATION, self.Status.AWAITING_CITIZEN_VERIFICATION, self.Status.REOPENED, self.Status.RESOLVED],
            self.Status.PROTOTYPE: [self.Status.PILOT, self.Status.DEPLOYED, self.Status.AWAITING_VERIFICATION, self.Status.AWAITING_CITIZEN_VERIFICATION, self.Status.REOPENED, self.Status.RESOLVED],
            self.Status.PILOT: [self.Status.DEPLOYED, self.Status.AWAITING_VERIFICATION, self.Status.AWAITING_CITIZEN_VERIFICATION, self.Status.REOPENED, self.Status.RESOLVED],
            self.Status.DEPLOYED: [self.Status.AWAITING_VERIFICATION, self.Status.AWAITING_CITIZEN_VERIFICATION, self.Status.REOPENED, self.Status.RESOLVED],
            self.Status.AWAITING_VERIFICATION: [self.Status.VERIFIED, self.Status.RESOLVED, self.Status.FAILED, self.Status.REOPENED, self.Status.DEPLOYED],
            self.Status.AWAITING_CITIZEN_VERIFICATION: [self.Status.VERIFIED, self.Status.RESOLVED, self.Status.FAILED, self.Status.REOPENED, self.Status.DEPLOYED],
            self.Status.VERIFIED: [self.Status.RESOLVED],
            self.Status.REOPENED: [self.Status.ADOPTED, self.Status.ASSIGNED, self.Status.PROJECT, self.Status.PILOT, self.Status.DEPLOYED, self.Status.RESOLVED],
            self.Status.FAILED: [self.Status.REOPENED, self.Status.ADOPTED],
        }

        if prev_status in [self.Status.REJECTED, self.Status.RESOLVED]:
            raise ValidationError(f"Cannot transition issue from terminal state '{prev_status}'.")

        allowed = VALID_TRANSITIONS.get(prev_status, [])
        if new_status not in allowed:
            raise ValidationError(f"Invalid transition for issue from '{prev_status}' to '{new_status}'. Allowed transitions: {allowed}")

        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])
        history = IssueStatusHistory.objects.create(
            issue=self,
            previous_status=prev_status,
            new_status=new_status,
            actor=actor,
            reason=reason or ''
        )
        log_activity(
            issue=self,
            actor=actor,
            event_type='STATUS_TRANSITION',
            description=f"Status changed from {prev_status} to {new_status}. {reason}".strip(),
            object_type='issue',
            object_id=str(self.id),
            metadata={'previous_status': prev_status, 'new_status': new_status, 'reason': reason or ''}
        )
        return history

    def __str__(self):
        return f"[{self.public_id or self.id}] [{self.get_status_display()}] {self.title} ({self.district})"


class IssueStatusHistory(models.Model):
    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name='status_history'
    )
    previous_status = models.CharField(max_length=30)
    new_status = models.CharField(max_length=30)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issue_status_changes'
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Issue #{self.issue_id}: {self.previous_status} -> {self.new_status} by {self.actor}"


class Adoption(models.Model):
    class Mode(models.TextChoices):
        SELF_ADOPTED = 'self_adopted', 'University Self-Adopted'
        NOMINATION_APPROVED = 'nomination_approved', 'Student Nomination Approved'

    class Status(models.TextChoices):
        APPROVED = 'approved', 'Approved'
        REQUESTED = 'requested', 'Requested'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'

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
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coordinated_adoptions',
        help_text="University coordinator who approved or adopted this issue"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.APPROVED
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
    approved_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when adoption was approved by coordinator")

    @property
    def challenge(self):
        """Specification Section 60 alias to issue."""
        return self.issue

    @challenge.setter
    def challenge(self, value):
        self.issue = value

    @property
    def created_at(self):
        """Specification Section 60 alias to adopted_at."""
        return self.adopted_at

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if self.status == self.Status.APPROVED and not self.approved_at:
            self.approved_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.university.name} adopted {self.issue.title}"


class StudentNomination(models.Model):
    """
    Tracks nomination requests sent by students to their university coordinator.
    Specification Section 59 ChallengeNomination model.
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

    @property
    def challenge(self):
        """Specification Section 59 alias to issue."""
        return self.issue

    @challenge.setter
    def challenge(self, value):
        self.issue = value

    class Meta:
        unique_together = ('issue', 'university', 'student')

    def __str__(self):
        return f"Nomination: {self.student.name} -> {self.issue.title} ({self.get_status_display()})"


# Specification Section 59 & 60 Model Aliases
ChallengeNomination = StudentNomination
ChallengeAdoption = Adoption


class OpenCall(models.Model):
    """
    Real backend representation of an Open Call for a challenge (P0 Issue 6).
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        UPCOMING = 'upcoming', 'Upcoming'
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'
        CANCELLED = 'cancelled', 'Cancelled'

    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name='open_calls'
    )
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='open_calls'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_open_calls'
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    opening_date = models.DateField(null=True, blank=True)
    closing_date = models.DateField(null=True, blank=True)
    eligibility = models.TextField(blank=True)
    required_skills = models.TextField(blank=True)
    departments = models.CharField(max_length=255, blank=True)
    funding = models.CharField(max_length=100, blank=True)
    evaluation_criteria = models.TextField(blank=True)
    max_teams = models.IntegerField(default=10)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def challenge(self):
        """Specification Section 61 alias to issue."""
        return self.issue

    @challenge.setter
    def challenge(self, value):
        self.issue = value

    def __str__(self):
        return f"Open Call: {self.title} ({self.university.name} - {self.get_status_display()})"


class CitizenVerification(models.Model):
    """
    Mandatory citizen verification gate recording the real field outcome (P0 Issue 10 & P1 Issue 36-37).
    """
    class Result(models.TextChoices):
        VERIFIED = 'verified', 'Verified Resolved'
        NOT_RESOLVED = 'not_resolved', 'Not Resolved'

    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name='citizen_verifications'
    )
    citizen = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verifications'
    )
    result = models.CharField(max_length=20, choices=Result.choices)
    reason = models.TextField(blank=True, help_text="Reason for verdict")
    what_is_still_wrong = models.TextField(blank=True, help_text="Detailed explanation of what remains unresolved")
    evidence = models.TextField(blank=True, help_text="Links, test readings, or proof")
    photo_video_url = models.URLField(max_length=500, blank=True, help_text="Photo or video URL evidencing unresolved condition")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def challenge(self):
        """Specification Section 69 alias to issue."""
        return self.issue

    @challenge.setter
    def challenge(self, value):
        self.issue = value

    def __str__(self):
        return f"CitizenVerification #{self.id} for Issue #{self.issue_id}: {self.get_result_display()} by {self.citizen}"


class ActivityEvent(models.Model):
    """
    Unified activity event timeline for a challenge repository (P0 Issue 8 & P1 Issue 38).
    """
    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name='activity_timeline'
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_events'
    )
    event_type = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    object_type = models.CharField(max_length=50, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def challenge(self):
        """Specification Section 68 alias to issue."""
        return self.issue

    @challenge.setter
    def challenge(self, value):
        self.issue = value

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.event_type}] Issue #{self.issue_id} by {self.actor}: {self.description[:50]}"


def log_activity(issue, actor, event_type, description='', object_type='', object_id='', metadata=None):
    return ActivityEvent.objects.create(
        issue=issue,
        actor=actor,
        event_type=event_type,
        description=description,
        object_type=object_type,
        object_id=str(object_id) if object_id else '',
        metadata=metadata or {}
    )


class DiscussionComment(models.Model):
    """
    Challenge, Solution & Project technical discussion system (Section 40 & P1 Issue 18 & 40).
    Supports discussions across challenges, solution proposals, and project implementation.
    """
    class TargetType(models.TextChoices):
        CHALLENGE = 'challenge', 'Challenge Discussion'
        SOLUTION = 'solution', 'Solution Technical Discussion'
        PROJECT = 'project', 'Project Technical Discussion'

    TargetType.ISSUE = TargetType.CHALLENGE
    TargetType.PITCH = TargetType.SOLUTION

    target_type = models.CharField(max_length=20, choices=TargetType.choices, default=TargetType.CHALLENGE)
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='discussions', null=True, blank=True)
    pitch = models.ForeignKey('pitches.Pitch', on_delete=models.CASCADE, related_name='discussions', null=True, blank=True)
    project = models.ForeignKey('pitches.Project', on_delete=models.CASCADE, related_name='discussions', null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='discussion_comments')
    category = models.CharField(
        max_length=30,
        default='general',
        help_text="Discussion topic category (Issue 41: clarification, context, requirements, constraints, evidence, technical, review, implementation, changes, mentorship, general)"
    )
    content = models.TextField(help_text="Discussion message, technical comment, or requirement inquiry")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def challenge(self):
        """Specification Section 67 alias to issue."""
        return self.issue

    @challenge.setter
    def challenge(self, value):
        self.issue = value

    @property
    def solution(self):
        """Specification Section 67 alias to pitch."""
        return self.pitch

    @solution.setter
    def solution(self, value):
        self.pitch = value

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.get_target_type_display()} [{self.category}] by {self.author}: {self.content[:40]}"


# Specification Section 67 Model Aliases
Discussion = DiscussionComment
Comment = DiscussionComment


class ChallengeCollaborator(models.Model):
    """
    Challenge Collaborators & repository permissions (Section 43).
    Supports roles: maintainer, coordinator, faculty, student_contributor, government, industry_partner, citizen_contributor.
    """
    class Role(models.TextChoices):
        MAINTAINER = 'maintainer', 'Maintainer'
        COORDINATOR = 'coordinator', 'University Coordinator'
        FACULTY = 'faculty', 'Faculty Mentor'
        STUDENT_CONTRIBUTOR = 'student_contributor', 'Student Contributor'
        GOVERNMENT = 'government', 'Government Authority'
        INDUSTRY_PARTNER = 'industry_partner', 'Industry Partner'
        CITIZEN_CONTRIBUTOR = 'citizen_contributor', 'Citizen Contributor'

    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='collaborators')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='challenge_collaborations')
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.CITIZEN_CONTRIBUTOR)
    permissions = models.JSONField(default=dict, blank=True, help_text="Custom collaborator permissions/capabilities")
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collaborators_added'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        unique_together = ('issue', 'user')

    def __str__(self):
        return f"{self.user} as {self.get_role_display()} on Issue #{self.issue_id}"


class IssueMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = 'image', 'Image Photo'
        VIDEO = 'video', 'Video Evidence'
        DOCUMENT = 'document', 'Document Report'
        EVIDENCE = 'evidence', 'Field Test Evidence'

    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='media_files')
    file = models.FileField(upload_to='issues/media/', blank=True, null=True)
    file_url = models.URLField(max_length=500, blank=True)
    media_type = models.CharField(max_length=20, choices=MediaType.choices, default=MediaType.IMAGE)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_issue_media'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"IssueMedia #{self.id} ({self.get_media_type_display()}) for Issue #{self.issue_id}"


class IssueDuplicate(models.Model):
    class Status(models.TextChoices):
        SUSPECTED = 'suspected', 'Suspected Duplicate'
        CONFIRMED = 'confirmed', 'Confirmed Duplicate'
        REJECTED = 'rejected', 'Not Duplicate'

    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='duplicate_sources')
    duplicate_issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='duplicate_targets')
    detection_method = models.CharField(max_length=50, default='AI_SIMILARITY')
    confidence_score = models.FloatField(default=0.0)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_duplicates'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUSPECTED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('issue', 'duplicate_issue')

    def __str__(self):
        return f"IssueDuplicate: #{self.issue_id} -> #{self.duplicate_issue_id} ({self.get_status_display()})"


class Deployment(models.Model):
    class Status(models.TextChoices):
        PLANNED = 'planned', 'Deployment Planned'
        IN_PROGRESS = 'in_progress', 'Field Deployment Active'
        COMPLETED = 'completed', 'Deployment Completed'
        FAILED = 'failed', 'Deployment Failed'

    project = models.ForeignKey('pitches.Project', on_delete=models.CASCADE, related_name='deployments')
    deployment_location = models.CharField(max_length=255)
    deployment_date = models.DateField(null=True, blank=True)
    version_deployed = models.CharField(max_length=50, default='v1.0')
    deployment_status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    authority = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_deployments'
    )
    evidence = models.TextField(blank=True, help_text="Links to test reports, photo/video evidence, telemetry")
    impact_metrics = models.JSONField(default=dict, blank=True, help_text="Measured outcome metrics e.g. beneficiaries, efficiency score")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Deployment #{self.id} for Project #{self.project_id} [{self.get_deployment_status_display()}]"


class Resolution(models.Model):
    issue = models.OneToOneField(Issue, on_delete=models.CASCADE, related_name='resolution_record')
    project = models.ForeignKey('pitches.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='resolutions')
    resolution_summary = models.TextField(help_text="Summary of how the societal challenge was solved")
    outcome = models.TextField(blank=True, help_text="Final field outcome and measurable social impact")
    resolved_at = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_resolutions'
    )
    evidence = models.TextField(blank=True, help_text="Verification links, documents or test readings")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Resolution for Issue #{self.issue_id} (Resolved {self.resolved_at.strftime('%Y-%m-%d')})"




