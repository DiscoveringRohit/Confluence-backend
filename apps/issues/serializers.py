from rest_framework import serializers
from .models import (
    Issue, Adoption, StudentNomination, IssueStatusHistory,
    OpenCall, CitizenVerification, ActivityEvent, DiscussionComment,
    ChallengeCollaborator
)
from apps.users.serializers import UserProfileSerializer, UniversitySerializer

class DiscussionCommentSerializer(serializers.ModelSerializer):
    author_details = UserProfileSerializer(source='author', read_only=True)
    challenge = serializers.IntegerField(source='issue_id', read_only=True)
    solution = serializers.IntegerField(source='pitch_id', read_only=True)

    class Meta:
        model = DiscussionComment
        fields = [
            'id', 'target_type', 'issue', 'challenge', 'pitch', 'solution', 'project',
            'author', 'author_details', 'category', 'content', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'author_details', 'challenge', 'solution', 'created_at', 'updated_at']


# Specification Section 67 Serializer Aliases
DiscussionSerializer = DiscussionCommentSerializer
CommentSerializer = DiscussionCommentSerializer


class ChallengeCollaboratorSerializer(serializers.ModelSerializer):
    user_details = UserProfileSerializer(source='user', read_only=True)
    added_by_details = UserProfileSerializer(source='added_by', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = ChallengeCollaborator
        fields = [
            'id', 'issue', 'user', 'user_details', 'role', 'role_display',
            'permissions', 'added_by', 'added_by_details', 'created_at'
        ]
        read_only_fields = ['id', 'issue', 'added_by', 'added_by_details', 'created_at']


class IssueStatusHistorySerializer(serializers.ModelSerializer):
    actor_details = UserProfileSerializer(source='actor', read_only=True)

    class Meta:
        model = IssueStatusHistory
        fields = ['id', 'issue', 'previous_status', 'new_status', 'actor', 'actor_details', 'reason', 'created_at']
        read_only_fields = ['id', 'created_at']


class AdoptionSerializer(serializers.ModelSerializer):
    university_details = UniversitySerializer(source='university', read_only=True)
    coordinator_details = UserProfileSerializer(source='coordinator', read_only=True)
    nominated_by_details = UserProfileSerializer(source='nominated_by', read_only=True)
    challenge = serializers.IntegerField(source='issue_id', read_only=True)
    created_at = serializers.DateTimeField(source='adopted_at', read_only=True)

    class Meta:
        model = Adoption
        fields = [
            'id', 'issue', 'challenge', 'university', 'university_details',
            'coordinator', 'coordinator_details', 'status', 'mode',
            'nominated_by', 'nominated_by_details', 'adopted_at', 'created_at', 'approved_at'
        ]
        read_only_fields = ['id', 'adopted_at', 'created_at', 'challenge']


class StudentNominationSerializer(serializers.ModelSerializer):
    student_details = UserProfileSerializer(source='student', read_only=True)
    university_details = UniversitySerializer(source='university', read_only=True)
    challenge = serializers.IntegerField(source='issue_id', read_only=True)

    class Meta:
        model = StudentNomination
        fields = [
            'id', 'issue', 'challenge', 'university', 'university_details',
            'student', 'student_details', 'rationale',
            'status', 'reviewed_at', 'created_at'
        ]
        read_only_fields = ['id', 'student', 'status', 'reviewed_at', 'created_at', 'challenge']


# Specification Section 59 & 60 Serializer Aliases
ChallengeNominationSerializer = StudentNominationSerializer
ChallengeAdoptionSerializer = AdoptionSerializer


class CitizenVerificationSerializer(serializers.ModelSerializer):
    citizen_details = UserProfileSerializer(source='citizen', read_only=True)
    challenge = serializers.IntegerField(source='issue_id', read_only=True)

    class Meta:
        model = CitizenVerification
        fields = [
            'id', 'issue', 'challenge', 'citizen', 'citizen_details', 'result',
            'reason', 'what_is_still_wrong', 'evidence', 'photo_video_url', 'created_at'
        ]
        read_only_fields = ['id', 'citizen', 'challenge', 'created_at']


class ActivityEventSerializer(serializers.ModelSerializer):
    actor_details = UserProfileSerializer(source='actor', read_only=True)
    challenge = serializers.IntegerField(source='issue_id', read_only=True)

    class Meta:
        model = ActivityEvent
        fields = ['id', 'issue', 'challenge', 'actor', 'actor_details', 'event_type', 'description', 'object_type', 'object_id', 'metadata', 'created_at']
        read_only_fields = ['id', 'challenge', 'created_at']


class OpenCallSerializer(serializers.ModelSerializer):
    university_details = UniversitySerializer(source='university', read_only=True)
    created_by_details = UserProfileSerializer(source='created_by', read_only=True)
    challenge = serializers.IntegerField(source='issue_id', read_only=True)

    class Meta:
        model = OpenCall
        fields = [
            'id', 'issue', 'challenge', 'university', 'university_details',
            'created_by', 'created_by_details', 'title', 'description',
            'opening_date', 'closing_date', 'eligibility', 'required_skills',
            'departments', 'funding', 'evaluation_criteria', 'max_teams',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'challenge', 'university', 'university_details', 'created_by', 'created_by_details', 'created_at', 'updated_at']


class IssueSerializer(serializers.ModelSerializer):
    submitted_by_details = UserProfileSerializer(source='submitted_by', read_only=True)
    created_by = serializers.IntegerField(source='submitted_by_id', read_only=True)
    validated_by_details = UserProfileSerializer(source='validated_by', read_only=True)
    maintaining_university_details = UniversitySerializer(source='maintaining_university', read_only=True)
    maintainer_university = serializers.IntegerField(source='maintaining_university_id', read_only=True)
    managed_by_details = UserProfileSerializer(source='managed_by', read_only=True)
    adoption_details = AdoptionSerializer(source='adoption', read_only=True)
    duplicate_of_details = serializers.SerializerMethodField()
    status_history = IssueStatusHistorySerializer(many=True, read_only=True)
    open_calls = OpenCallSerializer(many=True, read_only=True)
    citizen_verifications = CitizenVerificationSerializer(many=True, read_only=True)
    collaborators = ChallengeCollaboratorSerializer(many=True, read_only=True)
    ownership = serializers.ReadOnlyField()
    location = serializers.ReadOnlyField()

    class Meta:
        model = Issue
        fields = [
            'id', 'public_id', 'title', 'description', 'context', 'expected_outcome',
            'requirements', 'constraints', 'acceptance_criteria',
            'photo', 'photo_url', 'documents',
            'latitude', 'longitude', 'district', 'address', 'location',
            'category', 'ai_confidence', 'ai_triage_notes',
            'status', 'submitted_by', 'submitted_by_details', 'created_by',
            'validated_by', 'validated_by_details',
            'maintaining_university', 'maintaining_university_details', 'maintainer_university',
            'managed_by', 'managed_by_details',
            'ownership', 'collaborators',
            'duplicate_of', 'duplicate_of_details',
            'is_escalated', 'citizen_verified_resolved', 'citizen_feedback_on_resolution',
            'adoption_details', 'status_history', 'open_calls', 'citizen_verifications',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'public_id', 'submitted_by', 'created_by', 'ai_confidence', 'ai_triage_notes',
            'validated_by', 'validated_by_details',
            'maintaining_university', 'maintaining_university_details', 'maintainer_university',
            'managed_by', 'managed_by_details',
            'ownership', 'collaborators', 'location',
            'duplicate_of_details', 'adoption_details', 'status_history',
            'open_calls', 'citizen_verifications', 'created_at', 'updated_at'
        ]

    def get_duplicate_of_details(self, obj):
        if obj.duplicate_of:
            return {
                'id': obj.duplicate_of.id,
                'title': obj.duplicate_of.title,
                'status': obj.duplicate_of.status
            }
        return None

    def validate(self, data):
        # Mandatory photo requirement check as per specification
        photo = data.get('photo')
        photo_url = data.get('photo_url')
        if not photo and not photo_url and self.instance is None:
            raise serializers.ValidationError({"photo": "A photo or photo URL is required for issue verification."})
        return data


class IssueModerationSerializer(serializers.Serializer):
    action = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    duplicate_of_id = serializers.IntegerField(required=False, allow_null=True)
    category = serializers.ChoiceField(choices=Issue.Category.choices, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    moderation_notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        action = data.get('action')
        status_val = data.get('status')
        if not action and status_val:
            if status_val in ['validated', 'validate']:
                data['action'] = 'validate'
            elif status_val in ['rejected', 'reject']:
                data['action'] = 'reject'
            elif status_val in ['duplicate', 'mark_duplicate']:
                data['action'] = 'mark_duplicate'
            else:
                data['action'] = status_val
        if not data.get('action'):
            data['action'] = 'validate'
        if not data.get('notes') and data.get('moderation_notes'):
            data['notes'] = data.get('moderation_notes')
        return data

