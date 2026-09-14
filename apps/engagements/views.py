from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import IndustryEngagement
from .serializers import IndustryEngagementSerializer
from apps.issues.models import Issue
from apps.pitches.models import Pitch
from apps.users.models import User
from apps.notifications.models import Notification
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
                qs = qs.filter(status__in=['accepted', 'active', 'completed'])
            elif user.role == 'industry_partner':
                if user.organization:
                    qs = qs.filter(industry_org=user.organization)
                else:
                    qs = qs.filter(created_by=user)
            elif user.role in ['university_coordinator', 'faculty_mentor']:
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
        pitch = Pitch.objects.filter(issue=issue, status__in=[Pitch.Status.SELECTED, Pitch.Status.MERGED]).first()

        instance = serializer.save(
            created_by=user,
            initiator=initiator,
            industry_org=org,
            pitch=pitch
        )

        # Notify counterpart
        try:
            if initiator == IndustryEngagement.Initiator.INDUSTRY:
                if hasattr(issue, 'adoption') and issue.adoption and issue.adoption.university:
                    coords = User.objects.filter(university=issue.adoption.university, role='university_coordinator')
                    for coord in coords:
                        Notification.objects.create(
                            recipient=coord,
                            title=f"New Industry Partnership Proposal from {org.name}",
                            message=f"{org.name} proposed a {instance.get_engagement_type_display()} engagement for problem #{issue.id} ({issue.title[:40]}).",
                            notification_type=Notification.NotificationType.PROJECT,
                            link_url="/university/adopted-problems"
                        )
            else:
                partners = User.objects.filter(organization=org, role='industry_partner')
                for partner in partners:
                    Notification.objects.create(
                        recipient=partner,
                        title="University Innovation Outreach",
                        message=f"{user.university.name if user.university else 'University'} requested {instance.get_engagement_type_display()} for problem #{issue.id} ({issue.title[:40]}).",
                        notification_type=Notification.NotificationType.PROJECT,
                        link_url="/industry/engagements"
                    )
        except Exception:
            pass


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

        # Link selected pitch if one has been selected in the meantime
        if not engagement.pitch:
            selected_pitch = Pitch.objects.filter(issue=engagement.issue, status__in=[Pitch.Status.SELECTED, Pitch.Status.MERGED]).first()
            if selected_pitch:
                engagement.pitch = selected_pitch

        engagement.save()

        # Send notification to initiator
        try:
            if engagement.created_by:
                action_label = action.capitalize()
                Notification.objects.create(
                    recipient=engagement.created_by,
                    title=f"Industry Engagement {action_label}",
                    message=f"Engagement for Problem #{engagement.issue.id} was marked as {action_label} by {request.user.name or request.user.email}.",
                    notification_type=Notification.NotificationType.PROJECT,
                    link_url="/industry/engagements" if getattr(engagement.created_by, 'role', '') == 'industry_partner' else "/university/adopted-problems"
                )
        except Exception:
            pass

        return Response(IndustryEngagementSerializer(engagement).data)
