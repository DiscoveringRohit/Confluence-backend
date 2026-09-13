from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import IndustryEngagement
from .serializers import IndustryEngagementSerializer
from apps.issues.models import Issue
from apps.pitches.models import Pitch
from apps.users.permissions import (
    IsIndustryPartner,
    IsUniversityCoordinator,
)

class IndustryEngagementListCreateView(generics.ListCreateAPIView):
    serializer_class = IndustryEngagementSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        qs = IndustryEngagement.objects.select_related('issue', 'pitch', 'industry_org', 'created_by').all().order_by('-created_at')

        if user.is_authenticated:
            if user.role == 'student':
                return IndustryEngagement.objects.none()
            elif user.role == 'industry_partner':
                if user.organization:
                    qs = qs.filter(industry_org=user.organization)
                else:
                    qs = qs.filter(created_by=user)
            elif user.role == 'university_coordinator':
                if user.university:
                    qs = qs.filter(issue__adoption__university=user.university)

        issue_id = self.request.query_params.get('issue')
        if issue_id:
            qs = qs.filter(issue_id=issue_id)

        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated:
            raise PermissionDenied("Authentication required to propose an industry engagement.")
        issue = serializer.validated_data['issue']

        # Determine initiator
        if user.role == 'industry_partner':
            initiator = IndustryEngagement.Initiator.INDUSTRY
            org = user.organization
            if not org:
                raise ValidationError("Industry user must be affiliated with an organization.")
        elif user.role in ['university_coordinator', 'faculty_mentor']:
            initiator = IndustryEngagement.Initiator.UNIVERSITY
            org = serializer.validated_data.get('industry_org')
            if not org:
                raise ValidationError("Target industry organization must be specified.")
        else:
            raise PermissionDenied("Only industry partners or university coordinators can initiate partnerships.")

        # Find selected pitch if team already assigned
        pitch = Pitch.objects.filter(issue=issue, status=Pitch.Status.SELECTED).first()

        serializer.save(
            created_by=user,
            initiator=initiator,
            industry_org=org,
            pitch=pitch
        )


class RespondEngagementView(APIView):
    """
    Accept, decline, or activate an engagement request.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            engagement = IndustryEngagement.objects.get(pk=pk)
        except IndustryEngagement.DoesNotExist:
            return Response({'error': 'Engagement not found'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        response_notes = request.data.get('response_notes', '')

        if action not in ['accept', 'decline', 'activate', 'complete']:
            return Response({'error': 'Action must be accept, decline, activate, or complete'}, status=status.HTTP_400_BAD_REQUEST)

        action_map = {
            'accept': IndustryEngagement.Status.ACCEPTED,
            'decline': IndustryEngagement.Status.DECLINED,
            'activate': IndustryEngagement.Status.ACTIVE,
            'complete': IndustryEngagement.Status.COMPLETED,
        }

        engagement.status = action_map[action]
        if response_notes:
            engagement.response_notes = response_notes
        engagement.save()

        return Response(IndustryEngagementSerializer(engagement).data)
