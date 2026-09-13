import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.issues.models import Issue
from apps.users.models import University

class Pitch(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        UNDER_REVIEW = 'under_review', 'Under Review'
        SELECTED = 'selected', 'Selected'
        REJECTED = 'rejected', 'Rejected'
        MERGED = 'merged', 'Merged with Complementary Team'

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
    title = models.CharField(max_length=255, help_text="Short proposal/project title")
    
    # Student team (M2M)
    student_team = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='team_pitches',
        help_text="Student collaborators on this pitch"
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

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.submission_timestamp:
            self.submission_timestamp = timezone.now()
        if not self.submission_hash and self.confidential_package:
            timestamp_str = self.submission_timestamp.isoformat()
            payload = f"{self.confidential_package}@@{timestamp_str}".encode('utf-8')
            self.submission_hash = hashlib.sha256(payload).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Pitch: {self.title} for Issue #{self.issue_id} ({self.get_status_display()})"


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
