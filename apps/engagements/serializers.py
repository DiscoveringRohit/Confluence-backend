from rest_framework import serializers
from .models import IndustryEngagement
from apps.users.models import Organization
from apps.users.serializers import OrganizationSerializer, UserProfileSerializer
from apps.issues.serializers import IssueSerializer

class IndustryEngagementSerializer(serializers.ModelSerializer):
    industry_org_details = OrganizationSerializer(source='industry_org', read_only=True)
    industry_org = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all(), required=False)
    created_by_details = UserProfileSerializer(source='created_by', read_only=True)
    issue_title = serializers.CharField(source='issue.title', read_only=True)
    issue_status = serializers.CharField(source='issue.status', read_only=True)
    category = serializers.CharField(source='issue.category', read_only=True)
    district = serializers.CharField(source='issue.district', read_only=True)
    university_name = serializers.SerializerMethodField()
    pitch_title = serializers.CharField(source='pitch.title', read_only=True, allow_null=True)
    project_title = serializers.CharField(source='project.title', read_only=True, allow_null=True)

    class Meta:
        model = IndustryEngagement
        fields = [
            'id', 'issue', 'issue_title', 'issue_status', 'category', 'district',
            'university_name',
            'pitch', 'pitch_title', 'project', 'project_title',
            'industry_org', 'industry_org_details',
            'created_by', 'created_by_details',
            'engagement_type', 'initiator', 'status',
            'proposal_notes', 'response_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'status', 'initiator', 'created_at', 'updated_at']

    def get_university_name(self, obj):
        if hasattr(obj.issue, 'adoption') and obj.issue.adoption and obj.issue.adoption.university:
            return obj.issue.adoption.university.name
        return None
