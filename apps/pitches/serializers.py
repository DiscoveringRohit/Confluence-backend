from rest_framework import serializers
from .models import Pitch, CommunityFeedback, ProjectLifecycle
from apps.users.serializers import UserProfileSerializer, UniversitySerializer
from apps.issues.serializers import IssueSerializer, DiscussionCommentSerializer

class CommunityFeedbackSerializer(serializers.ModelSerializer):
    citizen_details = UserProfileSerializer(source='citizen', read_only=True)

    class Meta:
        model = CommunityFeedback
        fields = [
            'id', 'pitch', 'citizen', 'citizen_details',
            'feedback_text', 'relevance_score', 'mentor_notes',
            'is_shared_with_students', 'created_at'
        ]
        read_only_fields = ['id', 'citizen', 'created_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        # Relevance score & mentor notes are visible to university, mentor, and original author
        if not user or not user.is_authenticated:
            data.pop('relevance_score', None)
            data.pop('mentor_notes', None)
        elif user.role not in ['university_coordinator', 'faculty_mentor'] and user.id != instance.citizen_id:
            data.pop('relevance_score', None)
            data.pop('mentor_notes', None)

        return data


class ProjectLifecycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLifecycle
        fields = [
            'id', 'pitch', 'milestones', 'deliverables',
            'test_results', 'ip_records', 'outcome_status',
            'deployed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        is_team_member = user and user.is_authenticated and instance.pitch.student_team.filter(id=user.id).exists()
        is_uni = user and user.is_authenticated and getattr(user, 'role', None) in ['university_coordinator', 'faculty_mentor'] and user.university_id == instance.pitch.university_id
        is_assigned_mentor = user and user.is_authenticated and instance.pitch.assigned_mentor_id == user.id
        is_partner = user and user.is_authenticated and getattr(user, 'role', None) == 'industry_partner' and hasattr(instance.pitch, 'issue') and instance.pitch.issue.industry_engagements.filter(industry_org=user.organization, status__in=['active', 'accepted']).exists()

        if is_team_member or is_uni or is_assigned_mentor or is_partner:
            return data
        else:
            # Mask sensitive technical deliverables, milestones, and IP records for public/citizens/gov
            return {
                'id': data['id'],
                'pitch': data['pitch'],
                'outcome_status': data['outcome_status'],
                'deployed_at': data['deployed_at'],
                'status_note': 'Detailed milestones, deliverables, and IP records are restricted to project team and active partners.'
            }


from .models import (
    Pitch, CommunityFeedback, ProjectLifecycle, PitchVersionHistory,
    SolutionEvaluation, SolutionTeamMember, ReviewSession, Project, ProjectMilestone,
    Certificate, ProjectMember
)
from apps.issues.serializers import DiscussionCommentSerializer

class SolutionTeamMemberSerializer(serializers.ModelSerializer):
    student_details = UserProfileSerializer(source='student', read_only=True)
    solution = serializers.IntegerField(source='pitch_id', read_only=True)

    class Meta:
        model = SolutionTeamMember
        fields = ['id', 'pitch', 'solution', 'student', 'student_details', 'role', 'status', 'joined_at']
        read_only_fields = ['id', 'pitch', 'solution', 'student_details', 'joined_at']

    def validate(self, data):
        student = data.get('student')
        if student and getattr(student, 'role', None) != 'student':
            raise serializers.ValidationError({"student": "Team member must be a student."})
        return data


class ProjectMemberSerializer(serializers.ModelSerializer):
    user_details = UserProfileSerializer(source='user', read_only=True)

    class Meta:
        model = ProjectMember
        fields = ['id', 'project', 'user', 'user_details', 'role', 'joined_at', 'left_at']
        read_only_fields = ['id', 'project', 'user_details', 'joined_at']


# Specification Section 63 Serializer Alias
TeamMemberSerializer = SolutionTeamMemberSerializer


class SolutionEvaluationSerializer(serializers.ModelSerializer):
    reviewer_details = UserProfileSerializer(source='reviewer', read_only=True)
    solution = serializers.IntegerField(source='pitch_id', read_only=True)
    decision = serializers.CharField(source='recommendation', read_only=True)

    class Meta:
        model = SolutionEvaluation
        fields = [
            'id', 'pitch', 'solution', 'reviewer', 'reviewer_details',
            'technical_feasibility', 'social_impact', 'cost_feasibility',
            'scalability', 'sustainability', 'innovation', 'implementation_readiness',
            'total_score', 'recommendation', 'decision', 'comments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'pitch', 'solution', 'reviewer', 'total_score', 'decision', 'created_at', 'updated_at']

    def validate(self, data):
        # Validate score bounds
        bounds = {
            'technical_feasibility': 20,
            'social_impact': 20,
            'cost_feasibility': 15,
            'scalability': 15,
            'sustainability': 10,
            'innovation': 10,
            'implementation_readiness': 10,
        }
        for field, max_val in bounds.items():
            val = data.get(field, 0)
            if val < 0 or val > max_val:
                raise serializers.ValidationError({field: f"Score must be between 0 and {max_val}."})
        return data


# Specification Section 64 Serializer Alias
SolutionReviewSerializer = SolutionEvaluationSerializer


class PitchVersionHistorySerializer(serializers.ModelSerializer):
    actor_details = UserProfileSerializer(source='actor', read_only=True)

    class Meta:
        model = PitchVersionHistory
        fields = [
            'id', 'pitch', 'version', 'title', 'public_summary',
            'confidential_package', 'submission_hash', 'change_summary',
            'repository_url', 'demo_url', 'documentation_url', 'video_url',
            'actor', 'actor_details', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        is_own_team = user and user.is_authenticated and instance.pitch.student_team.filter(id=user.id).exists()
        is_assigned_mentor = user and user.is_authenticated and instance.pitch.assigned_mentor_id == user.id
        is_uni_coordinator = user and user.is_authenticated and getattr(user, 'role', None) in ['university_coordinator', 'faculty_mentor'] and user.university_id == instance.pitch.university_id

        if not (is_own_team or is_assigned_mentor or is_uni_coordinator):
            data['confidential_package'] = "[PROTECTED — Confidential Package]"

        return data


class PitchSerializer(serializers.ModelSerializer):
    challenge = serializers.IntegerField(source='issue_id', read_only=True)
    summary = serializers.CharField(source='public_summary', read_only=True)
    proposed_solution = serializers.CharField(source='public_summary', read_only=True)
    expected_impact = serializers.CharField(source='public_summary', read_only=True)
    private_details = serializers.CharField(source='confidential_package', read_only=True)
    student_team_details = UserProfileSerializer(source='student_team', many=True, read_only=True)
    team = serializers.PrimaryKeyRelatedField(source='student_team', many=True, read_only=True)
    collaborators = SolutionTeamMemberSerializer(many=True, read_only=True)
    university_details = UniversitySerializer(source='university', read_only=True)
    assigned_mentor_details = UserProfileSerializer(source='assigned_mentor', read_only=True)
    community_feedback = CommunityFeedbackSerializer(many=True, read_only=True)
    discussions = DiscussionCommentSerializer(many=True, read_only=True)
    project_lifecycle = ProjectLifecycleSerializer(read_only=True)
    version_history = PitchVersionHistorySerializer(many=True, read_only=True)
    evaluations = SolutionEvaluationSerializer(many=True, read_only=True)

    class Meta:
        model = Pitch
        fields = [
            'id', 'public_id', 'issue', 'challenge', 'university', 'university_details', 'open_call',
            'title', 'version', 'student_team', 'team', 'student_team_details', 'collaborators',
            'public_summary', 'summary', 'proposed_solution', 'expected_impact',
            'confidential_package', 'private_details',
            'repository_url', 'demo_url', 'documentation_url', 'video_url',
            'submission_hash', 'submission_timestamp', 'status',
            'assigned_mentor', 'assigned_mentor_details',
            'review_feedback', 'community_feedback', 'discussions', 'project_lifecycle',
            'version_history', 'evaluations', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'public_id', 'challenge', 'summary', 'proposed_solution', 'expected_impact',
            'private_details', 'team', 'submission_hash', 'submission_timestamp', 'status',
            'version', 'student_team_details', 'collaborators', 'university_details',
            'assigned_mentor_details', 'community_feedback', 'discussions',
            'project_lifecycle', 'version_history', 'evaluations', 'created_at', 'updated_at'
        ]

    def to_representation(self, instance):
        """
        Enforce Strict Access Control Matrix (SIH 2026 Problem #26043):
        - Issue report: Full for all
        - Pitch public summary: Full for all
        - Pitch confidential package: Full for own team, university, mentor; invited industry only. NO for citizens, competing teams, or government.
        - Community feedback: Full for university & mentor; student sees if shared by mentor; NO for other teams or industry; aggregated for government; own for citizen.
        - Project milestones / IP: Full for own team, university, mentor, partner industry; status-only for citizens & government.
        """
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        is_own_team = user and user.is_authenticated and instance.student_team.filter(id=user.id).exists()
        is_assigned_mentor = user and user.is_authenticated and instance.assigned_mentor_id == user.id
        is_uni_coordinator = user and user.is_authenticated and getattr(user, 'role', None) in ['university_coordinator', 'faculty_mentor'] and user.university_id == instance.university_id
        is_invited_industry = user and user.is_authenticated and getattr(user, 'role', None) == 'industry_partner' and instance.issue.industry_engagements.filter(industry_org=user.organization, status__in=['active', 'accepted']).exists()

        is_admin = user and user.is_authenticated and (user.is_staff or user.is_superuser or getattr(user, 'role', None) in ['admin'])

        # 1. Confidential Package Access
        allowed_confidential = is_own_team or is_assigned_mentor or is_uni_coordinator or is_invited_industry or is_admin
        if not allowed_confidential:
            data['confidential_package'] = "[PROTECTED — Visible only to submitting team, university review board, and assigned mentor]"

        # 2. Community Feedback Matrix Filtering
        cf_list = instance.community_feedback.all()
        user_role = getattr(user, 'role', None) if user and user.is_authenticated else None

        if not user or not user.is_authenticated:
            # Unauthenticated: public feedback comments only, scores hidden
            data['community_feedback'] = [
                {'id': f.id, 'feedback_text': f.feedback_text, 'created_at': f.created_at}
                for f in cf_list
            ]
        elif is_uni_coordinator or is_assigned_mentor:
            # Full feedback for university review board and assigned mentor
            pass
        elif is_own_team:
            # Student (own team): Only if shared by mentor
            shared_cf = [f for f in cf_list if f.is_shared_with_students]
            data['community_feedback'] = CommunityFeedbackSerializer(shared_cf, many=True, context=self.context).data
        elif user_role == 'student':
            # Student (other teams, same issue): No feedback visible
            data['community_feedback'] = []
        elif user_role == 'industry_partner':
            # Industry: No
            data['community_feedback'] = []
        elif user_role == 'gov_admin':
            # Government: Aggregated summary only
            data['community_feedback'] = [
                {
                    'id': f.id,
                    'created_at': f.created_at,
                    'relevance_score': f.relevance_score
                }
                for f in cf_list if f.relevance_score is not None
            ]
        elif user_role == 'citizen':
            # Citizen: Fellow citizen comments visible, but relevance score visible only for own feedback
            data['community_feedback'] = [
                {
                    'id': f.id,
                    'citizen_details': {'name': f.citizen.name},
                    'feedback_text': f.feedback_text,
                    'created_at': f.created_at,
                    **(({'relevance_score': f.relevance_score} if f.relevance_score else {}) if f.citizen_id == user.id else {})
                }
                for f in cf_list
            ]

        # 3. Project Lifecycle Filtering for Competing Student Teams
        if user_role == 'student' and not is_own_team:
            data['project_lifecycle'] = None

        # 4. Evaluations access filtering (P0 Issue 13)
        if not (is_own_team or is_assigned_mentor or is_uni_coordinator or (user and user.is_staff)):
            data['evaluations'] = []

        return data


from apps.users.models import User

from apps.issues.models import log_activity

class PitchCreateSerializer(serializers.ModelSerializer):
    team_member_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True
    )

    class Meta:
        model = Pitch
        fields = [
            'id', 'issue', 'open_call', 'title', 'public_summary',
            'confidential_package', 'repository_url', 'demo_url',
            'documentation_url', 'video_url', 'team_member_ids'
        ]

    def validate(self, attrs):
        user = self.context['request'].user
        issue = attrs['issue']

        if not user.university_id:
            raise serializers.ValidationError("Student must be affiliated with a university.")

        if not hasattr(issue, 'adoption') or issue.adoption.university_id != user.university_id:
            raise serializers.ValidationError("Students can only submit proposals for challenges adopted by their university.")

        open_call = attrs.get('open_call')
        if open_call and open_call.issue_id != issue.id:
            raise serializers.ValidationError({"open_call": "Open call must belong to the selected challenge."})

        team_member_ids = attrs.get('team_member_ids', [])
        if team_member_ids:
            members = User.objects.filter(id__in=team_member_ids)
            if members.count() != len(set(team_member_ids)):
                raise serializers.ValidationError({"team_member_ids": "One or more team member IDs are invalid."})
            for m in members:
                if m.role != 'student':
                    raise serializers.ValidationError({"team_member_ids": f"Team member {m.name or m.email} is not a student."})
                if m.university_id != user.university_id:
                    raise serializers.ValidationError({"team_member_ids": f"Team member {m.name or m.email} does not belong to {user.university.name}."})

        return attrs

    def create(self, validated_data):
        team_member_ids = validated_data.pop('team_member_ids', [])
        user = self.context['request'].user
        university = user.university

        pitch = Pitch.objects.create(university=university, **validated_data)
        pitch.student_team.add(user)
        SolutionTeamMember.objects.create(
            pitch=pitch,
            student=user,
            role=SolutionTeamMember.Role.OWNER,
            status=SolutionTeamMember.Status.ACTIVE
        )
        for member_id in team_member_ids:
            pitch.student_team.add(member_id)
            SolutionTeamMember.objects.create(
                pitch=pitch,
                student_id=member_id,
                role=SolutionTeamMember.Role.DEVELOPER,
                status=SolutionTeamMember.Status.ACTIVE
            )

        # Record initial version in solution history (P0 Issue 9 & P1 Issue 17)
        PitchVersionHistory.objects.create(
            pitch=pitch,
            version=pitch.version,
            title=pitch.title,
            public_summary=pitch.public_summary,
            confidential_package=pitch.confidential_package,
            repository_url=pitch.repository_url,
            demo_url=pitch.demo_url,
            documentation_url=pitch.documentation_url,
            video_url=pitch.video_url,
            submission_hash=pitch.submission_hash,
            change_summary="Initial proposal submission",
            actor=user
        )

        # Log to Activity Timeline (P0 Issue 8)
        try:
            log_activity(
                issue=pitch.issue,
                actor=user,
                event_type='SOLUTION_SUBMITTED',
                description=f"Student {user.name or user.email} submitted Solution #{pitch.id}: {pitch.title}",
                object_type='pitch',
                object_id=str(pitch.id)
            )
        except Exception:
            pass

        return pitch


class ReviewBoardActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['select_winner', 'merge_pitches', 'reject', 'assign_mentor', 'request_changes', 'start_review'])
    mentor_id = serializers.IntegerField(required=False, allow_null=True)
    merge_with_pitch_id = serializers.IntegerField(required=False, allow_null=True)
    review_feedback = serializers.CharField(required=False, allow_blank=True)


class PitchResubmitSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    public_summary = serializers.CharField(required=False)
    confidential_package = serializers.CharField(required=True)
    change_summary = serializers.CharField(required=True)
    repository_url = serializers.URLField(required=False, allow_blank=True)
    demo_url = serializers.URLField(required=False, allow_blank=True)
    documentation_url = serializers.URLField(required=False, allow_blank=True)
    video_url = serializers.URLField(required=False, allow_blank=True)


class ReviewSessionSerializer(serializers.ModelSerializer):
    created_by_details = UserProfileSerializer(source='created_by', read_only=True)
    challenge_title = serializers.CharField(source='challenge.title', read_only=True)
    pitch_title = serializers.CharField(source='pitch.title', read_only=True)

    class Meta:
        model = ReviewSession
        fields = [
            'id', 'university', 'challenge', 'challenge_title',
            'pitch', 'pitch_title', 'title', 'scheduled_at',
            'panelists', 'status', 'notes',
            'created_by', 'created_by_details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'university', 'created_by', 'created_at', 'updated_at']


class ProjectMilestoneSerializer(serializers.ModelSerializer):
    owner_details = UserProfileSerializer(source='owner', read_only=True)
    reviewer_details = UserProfileSerializer(source='reviewer', read_only=True)

    class Meta:
        model = ProjectMilestone
        fields = [
            'id', 'project', 'order', 'title', 'description', 'due_date',
            'owner', 'owner_details', 'status', 'evidence',
            'submitted_at', 'reviewed_at', 'reviewer', 'reviewer_details',
            'reviewer_feedback', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'submitted_at', 'reviewed_at', 'reviewer']


class ProjectSerializer(serializers.ModelSerializer):
    mentor_details = UserProfileSerializer(source='mentor', read_only=True)
    team_details = UserProfileSerializer(source='team', many=True, read_only=True)
    project_members = ProjectMemberSerializer(many=True, read_only=True)
    challenge_details = serializers.SerializerMethodField()
    solution_details = serializers.SerializerMethodField()
    progress_pct = serializers.SerializerMethodField()
    milestone_counts = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'public_id', 'solution', 'solution_details', 'challenge', 'challenge_details',
            'university', 'mentor', 'mentor_details', 'team', 'team_details', 'project_members',
            'title', 'status', 'start_date', 'target_date',
            'deployment_status', 'deployment_evidence', 'outcome',
            'deployed_at', 'progress_pct', 'milestone_counts',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'public_id', 'status', 'deployment_status',
            'deployment_evidence', 'outcome', 'deployed_at',
            'created_at', 'updated_at'
        ]

    def update(self, instance, validated_data):
        # Workflow and relationship bound fields cannot be mutated via PATCH/PUT (C-02)
        immutable_fields = [
            'solution', 'challenge', 'university', 'status',
            'deployment_status', 'deployment_evidence', 'outcome'
        ]
        for field in immutable_fields:
            validated_data.pop(field, None)
        return super().update(instance, validated_data)


    def get_challenge_details(self, obj):
        if obj.challenge:
            return {
                'id': obj.challenge.id,
                'public_id': getattr(obj.challenge, 'public_id', None),
                'title': obj.challenge.title,
                'category': obj.challenge.category,
                'district': obj.challenge.district,
                'status': obj.challenge.status,
            }
        return None

    def get_solution_details(self, obj):
        if obj.solution:
            return {
                'id': obj.solution.id,
                'public_id': getattr(obj.solution, 'public_id', None),
                'title': obj.solution.title,
                'status': obj.solution.status,
                'version': obj.solution.version,
                'repository_url': obj.solution.repository_url,
                'demo_url': obj.solution.demo_url,
            }
        return None

    def get_progress_pct(self, obj):
        milestones = obj.milestones.all()
        total = milestones.count()
        if total == 0:
            return 100 if obj.status in [
                Project.Status.DEPLOYED,
                Project.Status.AWAITING_CITIZEN_VERIFICATION,
                Project.Status.VERIFIED
            ] else 10
        approved = milestones.filter(status=ProjectMilestone.Status.APPROVED).count()
        return int((approved / total) * 100)

    def get_milestone_counts(self, obj):
        milestones = obj.milestones.all()
        return {
            'total': milestones.count(),
            'approved': milestones.filter(status=ProjectMilestone.Status.APPROVED).count(),
            'submitted': milestones.filter(status=ProjectMilestone.Status.SUBMITTED).count(),
            'pending': milestones.filter(status__in=[ProjectMilestone.Status.PENDING, ProjectMilestone.Status.IN_PROGRESS]).count(),
        }


class ProjectDetailSerializer(ProjectSerializer):
    milestones = ProjectMilestoneSerializer(many=True, read_only=True)
    discussions = DiscussionCommentSerializer(many=True, read_only=True)
    project_members = ProjectMemberSerializer(many=True, read_only=True)

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ['milestones', 'discussions', 'project_members']


class CertificateSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(source='recipient.name', read_only=True)
    recipient_email = serializers.CharField(source='recipient.email', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    challenge_title = serializers.CharField(source='challenge.title', read_only=True)
    solution_title = serializers.CharField(source='solution.title', read_only=True)
    university_name = serializers.CharField(source='project.university.name', read_only=True)
    verification_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            'id', 'certificate_id', 'recipient', 'recipient_name', 'recipient_email',
            'project', 'project_title', 'challenge', 'challenge_title',
            'solution', 'solution_title', 'university_name',
            'role', 'title', 'issued_at', 'verification_hash',
            'is_revoked', 'revocation_reason', 'verification_url'
        ]
        read_only_fields = fields

    def get_verification_url(self, obj):
        return f"/certificates/{obj.certificate_id}/verify"


# Specification Section 62 Serializer Aliases
SolutionSerializer = PitchSerializer
SolutionCreateSerializer = PitchCreateSerializer

