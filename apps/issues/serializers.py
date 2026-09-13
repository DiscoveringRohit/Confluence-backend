from rest_framework import serializers
from .models import Issue, Adoption, StudentNomination
from apps.users.serializers import UserProfileSerializer, UniversitySerializer

class AdoptionSerializer(serializers.ModelSerializer):
    university_details = UniversitySerializer(source='university', read_only=True)
    nominated_by_details = UserProfileSerializer(source='nominated_by', read_only=True)

    class Meta:
        model = Adoption
        fields = ['id', 'issue', 'university', 'university_details', 'mode', 'nominated_by', 'nominated_by_details', 'adopted_at']
        read_only_fields = ['id', 'adopted_at']


class StudentNominationSerializer(serializers.ModelSerializer):
    student_details = UserProfileSerializer(source='student', read_only=True)
    university_details = UniversitySerializer(source='university', read_only=True)

    class Meta:
        model = StudentNomination
        fields = [
            'id', 'issue', 'university', 'university_details',
            'student', 'student_details', 'rationale',
            'status', 'reviewed_at', 'created_at'
        ]
        read_only_fields = ['id', 'student', 'status', 'reviewed_at', 'created_at']


class IssueSerializer(serializers.ModelSerializer):
    submitted_by_details = UserProfileSerializer(source='submitted_by', read_only=True)
    adoption_details = AdoptionSerializer(source='adoption', read_only=True)
    duplicate_of_details = serializers.SerializerMethodField()

    class Meta:
        model = Issue
        fields = [
            'id', 'title', 'description', 'expected_outcome',
            'photo', 'photo_url', 'documents',
            'latitude', 'longitude', 'district', 'address',
            'category', 'ai_confidence', 'ai_triage_notes',
            'status', 'submitted_by', 'submitted_by_details',
            'duplicate_of', 'duplicate_of_details',
            'is_escalated', 'citizen_verified_resolved', 'citizen_feedback_on_resolution',
            'adoption_details', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'submitted_by', 'ai_confidence', 'ai_triage_notes',
            'duplicate_of_details', 'adoption_details',
            'created_at', 'updated_at'
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
    action = serializers.ChoiceField(choices=['validate', 'reject', 'mark_duplicate'])
    duplicate_of_id = serializers.IntegerField(required=False, allow_null=True)
    category = serializers.ChoiceField(choices=Issue.Category.choices, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
