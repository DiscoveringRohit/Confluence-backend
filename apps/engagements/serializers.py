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

    class Meta:
        model = IndustryEngagement
        fields = [
            'id', 'issue', 'issue_title', 'issue_status',
            'pitch', 'industry_org', 'industry_org_details',
            'created_by', 'created_by_details',
            'engagement_type', 'initiator', 'status',
            'proposal_notes', 'response_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'status', 'initiator', 'created_at', 'updated_at']
