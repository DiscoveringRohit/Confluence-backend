import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.issues.models import Issue
from apps.users.models import University

class Pitch(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        UNDER_REVIEW = 'under_review', 'Under Review'
        CHANGES_REQUESTED = 'changes_requested', 'Changes Requested'
        RESUBMITTED = 'resubmitted', 'Resubmitted'
        SELECTED = 'selected', 'Selected'
        REJECTED = 'rejected', 'Rejected'
        MERGED = 'merged', 'Merged with Complementary Team'
        PROJECT = 'project', 'Active Implementation Project'

    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name='pitches'
    )
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='student_pitches'
    )
    open_call = models.ForeignKey(
        'issues.OpenCall',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pitches',
        help_text="Associated university open call if submitted against one"
    )
    public_id = models.CharField(max_length=50, blank=True, null=True, unique=True, db_index=True)
    title = models.CharField(max_length=255, help_text="Short proposal/project title")
    version = models.IntegerField(default=1, help_text="Current solution revision version")
    
    # Student team (M2M)
    student_team = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='team_pitches',
        help_text="Student collaborators on this pitch"
    )
    team_entity = models.ForeignKey(
        'SolutionTeamGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pitches',
        help_text="Associated SolutionTeamGroup model instance"
    )

    # DUAL-PACKAGE MODEL
    public_summary = models.TextField(
        help_text="Public approach + expected outcome. No technical implementation detail. Visible to citizens for feedback."
    )
    confidential_package = models.TextField(
        help_text="Technical design, architecture, prototype details, code references. Strictly isolated."
    )

    # Cryptographic proof-of-prior-art
    submission_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of confidential package + timestamp generated at submission"
    )
    submission_timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="Immutable timestamp at submission for prior-art protection audit trail"
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.SUBMITTED,
        db_index=True
    )
    assigned_mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mentored_pitches'
    )

    # For constructive feedback on rejected pitches
    review_feedback = models.TextField(blank=True, help_text="Constructive learning feedback from review board")
    merged_into = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_merged_pitches'
    )

    # Repository, Demo & Documentation Links (Section 17 & 21 & P1 Issue 17)
    repository_url = models.URLField(blank=True, help_text="GitHub or GitLab repository URL")
    demo_url = models.URLField(blank=True, help_text="Live demo, deployed prototype, or interactive sandbox URL")
    documentation_url = models.URLField(blank=True, help_text="Technical documentation, schema, or architecture whitepaper URL")
    video_url = models.URLField(blank=True, help_text="Demo or walkthrough video URL")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def challenge(self):
        """Specification Section 62 alias to issue."""
        return self.issue

    @challenge.setter
    def challenge(self, value):
        self.issue = value

    @property
    def summary(self):
        """Specification Section 62 alias to public_summary."""
        return self.public_summary

    @summary.setter
    def summary(self, value):
        self.public_summary = value

    @property
    def proposed_solution(self):
        """Specification Section 62 alias to public_summary."""
        return self.public_summary

    @proposed_solution.setter
    def proposed_solution(self, value):
        self.public_summary = value

    @property
    def expected_impact(self):
        """Specification Section 62 alias to public_summary / impact."""
        return self.public_summary

    @expected_impact.setter
    def expected_impact(self, value):
        self.public_summary = value

    @property
    def private_details(self):
        """Specification Section 62 alias to confidential_package."""
        return self.confidential_package

    @private_details.setter
    def private_details(self, value):
        self.confidential_package = value

    @property
    def team(self):
        """Specification Section 62 alias to student_team."""
        return self.student_team

    def compute_hash(self):
        timestamp_str = self.submission_timestamp.isoformat() if self.submission_timestamp else timezone.now().isoformat()
        payload = f"{self.confidential_package}@@{timestamp_str}@@v{self.version}".encode('utf-8')
        return hashlib.sha256(payload).hexdigest()

    def save(self, *args, **kwargs):
        if not self.submission_timestamp:
            self.submission_timestamp = timezone.now()
        if not self.submission_hash and self.confidential_package:
            self.submission_hash = self.compute_hash()
        super().save(*args, **kwargs)
        if not self.public_id and self.id:
            self.public_id = f"SOL-{self.id:04d}"
            super().save(update_fields=['public_id'])

    def __str__(self):
        return f"Pitch [{self.public_id or self.id}]: {self.title} for Issue #{self.issue_id} (v{self.version} - {self.get_status_display()})"


# Specification Section 62 & 63 Model Aliases
Solution = Pitch
SolutionTeam = Pitch


class PitchVersionHistory(models.Model):
    """
    Immutable versioned solution history tracking revisions (P0 Issue 9).
    """
    pitch = models.ForeignKey(
        Pitch,
        on_delete=models.CASCADE,
        related_name='version_history'
    )
    version = models.IntegerField(default=1)
    title = models.CharField(max_length=255)
    public_summary = models.TextField()
    confidential_package = models.TextField()
    submission_hash = models.CharField(max_length=64, blank=True)
    change_summary = models.TextField(blank=True)
    repository_url = models.URLField(blank=True)
    demo_url = models.URLField(blank=True)
    documentation_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pitch_version_updates'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']

    def __str__(self):
        return f"Pitch #{self.pitch_id} v{self.version} by {self.actor}"


class SolutionTeamMember(models.Model):
    """
    Structured solution team member model with roles and statuses (Section 22 & P1 Issue 20).
    """
    class Role(models.TextChoices):
        OWNER = 'owner', 'Project Lead / Owner'
        DEVELOPER = 'developer', 'Core Developer / Engineer'
        DESIGNER = 'designer', 'UI/UX & Hardware Designer'
        RESEARCHER = 'researcher', 'Field & Domain Researcher'
        OTHER = 'other', 'Contributor'

    class Status(models.TextChoices):
        INVITED = 'invited', 'Invited'
        ACTIVE = 'active', 'Active'
        REMOVED = 'removed', 'Removed'

    pitch = models.ForeignKey(
        Pitch,
        on_delete=models.CASCADE,
        related_name='collaborators'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='solution_collaborations'
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.DEVELOPER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    joined_at = models.DateTimeField(auto_now_add=True)

    @property
    def solution(self):
        """Specification Section 63 alias to pitch."""
        return self.pitch

    @solution.setter
    def solution(self, value):
        self.pitch = value

    class Meta:
        unique_together = ('pitch', 'student')

    def __str__(self):
        return f"{self.student} as {self.get_role_display()} on Solution #{self.pitch_id}"


# Specification Section 63 Model Alias
TeamMember = SolutionTeamMember



class CommunityFeedback(models.Model):
    pitch = models.ForeignKey(
        Pitch,
        on_delete=models.CASCADE,
        related_name='community_feedback'
    )
    citizen = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='citizen_pitch_feedback'
    )
    feedback_text = models.TextField()
    relevance_score = models.IntegerField(
        null=True,
        blank=True,
        help_text="Relevance score (1-10) assigned by faculty mentor / university review board"
    )
    mentor_notes = models.TextField(blank=True)
    is_shared_with_students = models.BooleanField(
        default=False,
        help_text="Mentor decides whether to share this community feedback with the student team"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback by {self.citizen.name} on Pitch #{self.pitch_id} (Score: {self.relevance_score})"


class ProjectLifecycle(models.Model):
    class OutcomeStatus(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        DEPLOYED = 'deployed', 'Deployed in Field'
        ABANDONED = 'abandoned', 'Abandoned'

    pitch = models.OneToOneField(
        Pitch,
        on_delete=models.CASCADE,
        related_name='project_lifecycle'
    )
    milestones = models.JSONField(
        default=list,
        help_text="Ordered list of milestone dicts: [{'title': str, 'due_date': str, 'completed': bool}]"
    )
    deliverables = models.TextField(blank=True, help_text="Summary of code/hardware/documentation deliverables")
    test_results = models.TextField(blank=True, help_text="Field validation and testing metrics")
    ip_records = models.TextField(blank=True, help_text="Patents, copyright, or tech transfer agreements")
    outcome_status = models.CharField(
        max_length=30,
        choices=OutcomeStatus.choices,
        default=OutcomeStatus.IN_PROGRESS
    )
    deployed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Lifecycle for Pitch #{self.pitch_id} ({self.get_outcome_status_display()})"


class SolutionEvaluation(models.Model):
    """
    Real persistence for solution evaluations / review board scoring (P0 Issue 12).
    Tracks multi-criteria scores, comments, reviewer, and recommendation.
    """
    class Recommendation(models.TextChoices):
        SELECT = 'select', 'Select as Winner'
        REQUEST_CHANGES = 'request_changes', 'Request Changes / Revisions'
        MERGE = 'merge', 'Merge with Another Pitch'
        REJECT = 'reject', 'Reject'

    pitch = models.ForeignKey(
        Pitch,
        on_delete=models.CASCADE,
        related_name='evaluations'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_evaluations'
    )
    # Multi-criteria scoring (Total 100 points)
    technical_feasibility = models.IntegerField(default=0, help_text="Technical Feasibility (0-20)")
    social_impact = models.IntegerField(default=0, help_text="Social Impact (0-20)")
    cost_feasibility = models.IntegerField(default=0, help_text="Cost & Budget (0-15)")
    scalability = models.IntegerField(default=0, help_text="Scalability (0-15)")
    sustainability = models.IntegerField(default=0, help_text="Environmental/Operational Sustainability (0-10)")
    innovation = models.IntegerField(default=0, help_text="Novelty & Innovation (0-10)")
    implementation_readiness = models.IntegerField(default=0, help_text="Implementation Readiness (0-10)")

    total_score = models.IntegerField(default=0, help_text="Calculated sum (0-100)")
    recommendation = models.CharField(
        max_length=30,
        choices=Recommendation.choices,
        default=Recommendation.REQUEST_CHANGES
    )
    comments = models.TextField(blank=True, help_text="Detailed evaluation critique or feedback")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def solution(self):
        """Specification Section 64 alias to pitch."""
        return self.pitch

    @solution.setter
    def solution(self, value):
        self.pitch = value

    @property
    def decision(self):
        """Specification Section 64 alias to recommendation."""
        return self.recommendation

    @decision.setter
    def decision(self, value):
        self.recommendation = value

    class Meta:
        ordering = ['-created_at']
        unique_together = ('pitch', 'reviewer')

    def calculate_total(self):
        return (
            self.technical_feasibility +
            self.social_impact +
            self.cost_feasibility +
            self.scalability +
            self.sustainability +
            self.innovation +
            self.implementation_readiness
        )

    def save(self, *args, **kwargs):
        self.total_score = self.calculate_total()
        if 'update_fields' in kwargs and kwargs['update_fields'] is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'total_score'}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Evaluation of Pitch #{self.pitch_id} by {self.reviewer} ({self.total_score}/100 - {self.get_recommendation_display()})"


# Specification Section 64 Model Alias
SolutionReview = SolutionEvaluation


class ReviewSession(models.Model):
    """
    Real persistence for scheduled university review boards (Issue 31).
    """
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='review_sessions'
    )
    challenge = models.ForeignKey(
        Issue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='review_sessions'
    )
    pitch = models.ForeignKey(
        Pitch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='review_sessions'
    )
    title = models.CharField(max_length=255)
    scheduled_at = models.DateTimeField()
    panelists = models.TextField(blank=True, help_text="Invited panel members, evaluators, or faculty")
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.SCHEDULED
    )
    notes = models.TextField(blank=True, help_text="Agenda, scoring instructions, or post-session minutes")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_review_sessions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f"ReviewSession: {self.title} ({self.scheduled_at.strftime('%Y-%m-%d %H:%M') if self.scheduled_at else 'TBD'}) - {self.get_status_display()}"


class Project(models.Model):
    """
    Dedicated implementation container for selected solutions (Issue 32 & 33).
    Tracks canonical project states from Planning to Citizen Verification.
    """
    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        PLANNING = 'planning', 'Planning & Architecture Freeze'
        PROTOTYPE = 'prototype', 'Prototype Development'
        PILOT = 'pilot', 'Field Pilot Testing'
        DEPLOYMENT_READY = 'deployment_ready', 'Deployment Ready'
        DEPLOYED = 'deployed', 'Deployed in Field'
        AWAITING_CITIZEN_VERIFICATION = 'awaiting_citizen_verification', 'Awaiting Citizen Verification'
        VERIFIED = 'verified', 'Verified by Citizen'
        REOPENED = 'reopened', 'Reopened'
        CLOSED = 'closed', 'Closed'

    solution = models.OneToOneField(
        Pitch,
        on_delete=models.CASCADE,
        related_name='project'
    )
    challenge = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name='projects'
    )
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name='projects'
    )
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mentored_projects'
    )
    team = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='assigned_projects',
        blank=True
    )
    public_id = models.CharField(max_length=50, blank=True, null=True, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.PLANNING
    )
    start_date = models.DateField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    deployment_status = models.CharField(max_length=50, default='pending', blank=True)
    deployment_evidence = models.TextField(blank=True, help_text="Deployment verification reports, photos, hardware specs")
    outcome = models.TextField(blank=True, help_text="Final deployment impact and findings")
    deployed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.public_id and self.id:
            self.public_id = f"PRJ-{self.id:04d}"
            super().save(update_fields=['public_id'])

    def __str__(self):
        return f"Project [{self.public_id or self.id}]: {self.title} [{self.get_status_display()}]"

    def transition_status(self, new_status, actor=None, reason='', extra_update_fields=None):
        if self.status == new_status:
            return

        VALID_TRANSITIONS = {
            self.Status.CREATED: [self.Status.PLANNING, self.Status.PROTOTYPE],
            self.Status.PLANNING: [self.Status.PROTOTYPE, self.Status.PILOT, self.Status.DEPLOYMENT_READY, self.Status.DEPLOYED],
            self.Status.PROTOTYPE: [self.Status.PILOT, self.Status.DEPLOYMENT_READY, self.Status.DEPLOYED],
            self.Status.PILOT: [self.Status.DEPLOYMENT_READY, self.Status.DEPLOYED, self.Status.AWAITING_CITIZEN_VERIFICATION],
            self.Status.DEPLOYMENT_READY: [self.Status.DEPLOYED, self.Status.PILOT, self.Status.AWAITING_CITIZEN_VERIFICATION, self.Status.VERIFIED, self.Status.REOPENED],
            self.Status.DEPLOYED: [self.Status.AWAITING_CITIZEN_VERIFICATION, self.Status.VERIFIED, self.Status.REOPENED],
            self.Status.AWAITING_CITIZEN_VERIFICATION: [self.Status.VERIFIED, self.Status.REOPENED, self.Status.DEPLOYED],
            self.Status.VERIFIED: [self.Status.CLOSED, self.Status.REOPENED],
            self.Status.REOPENED: [self.Status.PILOT, self.Status.PROTOTYPE, self.Status.PLANNING, self.Status.DEPLOYMENT_READY],
        }

        if self.status == self.Status.CLOSED:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Cannot transition project from terminal state '{self.status}'.")

        allowed = VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Invalid project transition from '{self.status}' to '{new_status}'. Allowed transitions: {allowed}")

        from apps.issues.models import log_activity
        old_status = self.status
        self.status = new_status
        if new_status == self.Status.DEPLOYED and not self.deployed_at:
            self.deployed_at = timezone.now()
        fields = {'status', 'deployed_at', 'updated_at'}
        if extra_update_fields:
            fields.update(extra_update_fields)
        self.save(update_fields=list(fields))
        try:
            log_activity(
                issue=self.challenge,
                actor=actor,
                event_type='project_status_changed',
                description=f"Project #{self.id} transitioned from {old_status} to {new_status}. {reason}".strip(),
                object_type='project',
                object_id=str(self.id),
                metadata={
                    'previous_status': old_status,
                    'new_status': new_status,
                    'reason': reason
                }
            )
        except Exception:
            pass
        return self


class ProjectMilestone(models.Model):
    """
    Measurable deliverables mapped to a Project container (Issue 34).
    Faculty Mentors evaluate and approve/reject milestone submissions.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        IN_PROGRESS = 'in_progress', 'In Progress'
        SUBMITTED = 'submitted', 'Submitted for Review'
        CHANGES_REQUESTED = 'changes_requested', 'Changes Requested'
        APPROVED = 'approved', 'Approved'
        OVERDUE = 'overdue', 'Overdue'

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='milestones'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING
    )
    due_date = models.CharField(max_length=100, blank=True, null=True, default='', help_text="Target date or relative timeframe e.g. '30 days'")
    evidence = models.TextField(blank=True, help_text="Evidence URL, demo video, or telemetry logs")
    submitted_at = models.DateTimeField(blank=True, null=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewer_feedback = models.TextField(blank=True, help_text="Mentor feedback or revision requests")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_milestones'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_milestones'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def reviewed_by(self):
        return self.reviewer

    @reviewed_by.setter
    def reviewed_by(self, value):
        self.reviewer = value

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Milestone #{self.order}: {self.title} on Project #{self.project_id} [{self.get_status_display()}]"


class Certificate(models.Model):
    """
    Verified Outcome Certificate (Section 55).
    Strict eligibility: Solution Selected + Project Completed + Deployment Evidence Approved + Citizen Verification Completed.
    Cryptographically sealed with SHA-256 tamper-proof verification hash.
    """
    class Role(models.TextChoices):
        STUDENT_INNOVATOR = 'student_innovator', 'Student Innovator'
        FACULTY_MENTOR = 'faculty_mentor', 'Faculty Mentor'
        COORDINATOR = 'coordinator', 'University Coordinator'
        INDUSTRY_PARTNER = 'industry_partner', 'Industry Innovation Partner'

    RoleType = Role

    certificate_id = models.CharField(max_length=64, unique=True, db_index=True)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates'
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='certificates'
    )
    challenge = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name='certificates'
    )
    solution = models.ForeignKey(
        Pitch,
        on_delete=models.CASCADE,
        related_name='certificates'
    )
    role = models.CharField(max_length=40, choices=Role.choices, default=Role.STUDENT_INNOVATOR)
    title = models.CharField(max_length=255, default="Certificate of Verified Civic Innovation & Field Deployment")
    issued_at = models.DateTimeField(auto_now_add=True)
    verification_hash = models.CharField(max_length=64, unique=True, help_text="Cryptographic SHA-256 seal")
    is_revoked = models.BooleanField(default=False)
    revocation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-issued_at']
        unique_together = ('project', 'recipient')

    def __str__(self):
        return f"Certificate {self.certificate_id}: {self.recipient.name} ({self.get_role_display()})"


class SolutionTeamGroup(models.Model):
    name = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_solution_teams'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pitches_solutionteam'

    def __str__(self):
        return f"SolutionTeamGroup: {self.name} (by {self.created_by.name if hasattr(self.created_by, 'name') else self.created_by.email})"


# Canonical Section 62 & 84 Aliases
SolutionTeam = Pitch
TeamMember = SolutionTeamMember


class ProjectMember(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='project_members')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assigned_project_memberships')
    role = models.CharField(max_length=50, default='Developer')
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('project', 'user')

    def __str__(self):
        return f"ProjectMember: {self.user.name if hasattr(self.user, 'name') else self.user.email} ({self.role}) on Project #{self.project_id}"


class ProjectDeliverable(models.Model):
    class DeliverableType(models.TextChoices):
        CODE = 'code', 'Source Code / Repository'
        HARDWARE = 'hardware', 'Hardware Design & Schematics'
        DOCUMENTATION = 'documentation', 'Technical Specification & Whitepaper'
        REPORT = 'report', 'Testing Report & Field Outcome'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='deliverables')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    deliverable_type = models.CharField(max_length=30, choices=DeliverableType.choices, default=DeliverableType.DOCUMENTATION)
    file = models.FileField(upload_to='projects/deliverables/', blank=True, null=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_deliverables'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Deliverable: {self.title} for Project #{self.project_id}"


class MentorAssignment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active Mentorship'
        COMPLETED = 'completed', 'Mentorship Completed'
        RELEASED = 'released', 'Released'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='mentor_assignments')
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='faculty_mentor_assignments'
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments_created'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MentorAssignment: {self.mentor.name if hasattr(self.mentor, 'name') else self.mentor.email} -> Project #{self.project_id} [{self.get_status_display()}]"



