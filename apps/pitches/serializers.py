from rest_framework import serializers
from .models import Pitch, CommunityFeedback, ProjectLifecycle
from apps.users.serializers import UserProfileSerializer, UniversitySerializer
from apps.issues.serializers import IssueSerializer

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
        is_uni = user and user.is_authenticated and user.role in ['university_coordinator', 'faculty_mentor'] and user.university_id == instance.pitch.university_id
        is_assigned_mentor = user and user.is_authenticated and instance.pitch.assigned_mentor_id == user.id
        is_partner = user and user.is_authenticated and user.role == 'industry_partner' and hasattr(instance.pitch, 'issue') and instance.pitch.issue.engagements.filter(industry_org=user.organization, status__in=['active', 'accepted']).exists()

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


class PitchSerializer(serializers.ModelSerializer):
    student_team_details = UserProfileSerializer(source='student_team', many=True, read_only=True)
    university_details = UniversitySerializer(source='university', read_only=True)
    assigned_mentor_details = UserProfileSerializer(source='assigned_mentor', read_only=True)
    community_feedback = CommunityFeedbackSerializer(many=True, read_only=True)
    project_lifecycle = ProjectLifecycleSerializer(read_only=True)

    class Meta:
        model = Pitch
        fields = [
            'id', 'issue', 'university', 'university_details',
            'title', 'student_team', 'student_team_details',
            'public_summary', 'confidential_package',
            'submission_hash', 'submission_timestamp', 'status',
            'assigned_mentor', 'assigned_mentor_details',
            'review_feedback', 'community_feedback', 'project_lifecycle',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'submission_hash', 'submission_timestamp', 'status',
            'student_team_details', 'university_details',
            'assigned_mentor_details', 'community_feedback',
            'project_lifecycle', 'created_at', 'updated_at'
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
        is_uni_coordinator = user and user.is_authenticated and user.role in ['university_coordinator', 'faculty_mentor'] and user.university_id == instance.university_id
        is_invited_industry = user and user.is_authenticated and user.role == 'industry_partner' and instance.issue.engagements.filter(industry_org=user.organization, status__in=['active', 'accepted']).exists()

        # 1. Confidential Package Access
        allowed_confidential = is_own_team or is_assigned_mentor or is_uni_coordinator or is_invited_industry
        if not allowed_confidential:
            data['confidential_package'] = "[PROTECTED — Visible only to submitting team, university review board, and assigned mentor]"

        # 2. Community Feedback Matrix Filtering
        cf_list = instance.community_feedback.all()
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
        elif user.role == 'student':
            # Student (other teams, same issue): No feedback visible
            data['community_feedback'] = []
        elif user.role == 'industry_partner':
            # Industry: No
            data['community_feedback'] = []
        elif user.role == 'gov_admin':
            # Government: Aggregated summary only
            data['community_feedback'] = [
                {
                    'id': f.id,
                    'created_at': f.created_at,
                    'relevance_score': f.relevance_score
                }
                for f in cf_list if f.relevance_score is not None
            ]
        elif user.role == 'citizen':
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
        if user and user.role == 'student' and not is_own_team:
            data['project_lifecycle'] = None

        return data


class PitchCreateSerializer(serializers.ModelSerializer):
    team_member_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True
    )

    class Meta:
        model = Pitch
        fields = [
            'id', 'issue', 'title', 'public_summary',
            'confidential_package', 'team_member_ids'
        ]

    def create(self, validated_data):
        team_member_ids = validated_data.pop('team_member_ids', [])
        user = self.context['request'].user
        issue = validated_data['issue']
        university = user.university or (issue.adoption.university if hasattr(issue, 'adoption') else None)

        if not university:
            raise serializers.ValidationError("A university must be associated with the submission.")

        pitch = Pitch.objects.create(university=university, **validated_data)
        pitch.student_team.add(user)
        for member_id in team_member_ids:
            pitch.student_team.add(member_id)

        return pitch


class ReviewBoardActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['select_winner', 'merge_pitches', 'reject', 'assign_mentor'])
    mentor_id = serializers.IntegerField(required=False, allow_null=True)
    merge_with_pitch_id = serializers.IntegerField(required=False, allow_null=True)
    review_feedback = serializers.CharField(required=False, allow_blank=True)
