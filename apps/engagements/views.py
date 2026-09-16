from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import IndustryEngagement
from .serializers import IndustryEngagementSerializer
from apps.issues.models import Issue, ChallengeCollaborator
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
            if not hasattr(issue, 'adoption') or issue.adoption.university_id != user.university_id:
                raise PermissionDenied("University coordinators can only initiate partnerships for challenges adopted by their university.")
        else:
            raise PermissionDenied("Only industry partners or university coordinators can initiate partnerships.")

        # Find project and pitch if available
        pitch = serializer.validated_data.get('pitch')
        if not pitch:
            pitch = Pitch.objects.filter(issue=issue, status__in=[Pitch.Status.SELECTED, Pitch.Status.MERGED]).first()

        project = serializer.validated_data.get('project')
        if not project:
            if pitch and hasattr(pitch, 'project'):
                project = pitch.project
            elif hasattr(issue, 'projects'):
                project = issue.projects.first()

        instance = serializer.save(
            created_by=user,
            initiator=initiator,
            industry_org=org,
            pitch=pitch,
            project=project
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
    Strict participant authorization enforced (P0 Issue 4).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            engagement = IndustryEngagement.objects.select_related('issue', 'issue__adoption', 'industry_org').get(pk=pk)
        except IndustryEngagement.DoesNotExist:
            return Response({'error': 'Engagement not found'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        response_notes = request.data.get('response_notes', '')

        if action not in ['accept', 'decline', 'activate', 'complete']:
            return Response({'error': 'Action must be accept, decline, activate, or complete'}, status=status.HTTP_400_BAD_REQUEST)

        # Participant Authorization Verification
        user = request.user
        is_staff = user.is_staff or getattr(user, 'role', '') == 'gov_admin'
        is_target_industry = (
            getattr(user, 'role', '') == 'industry_partner' and
            user.organization_id is not None and
            user.organization_id == engagement.industry_org_id
        )
        has_adoption = hasattr(engagement.issue, 'adoption') and engagement.issue.adoption is not None
        is_adopting_coordinator = (
            getattr(user, 'role', '') == 'university_coordinator' and
            user.university_id is not None and
            (
                (has_adoption and engagement.issue.adoption.university_id == user.university_id) or
                (engagement.pitch and engagement.pitch.university_id == user.university_id) or
                not has_adoption
            )
        )

        if action in ['accept', 'decline']:
            if engagement.initiator == IndustryEngagement.Initiator.INDUSTRY:
                # Industry proposed -> University coordinator must accept/decline
                if not (is_adopting_coordinator or is_staff):
                    raise PermissionDenied("Only the coordinator of the adopting university can accept or decline this engagement.")
            else:
                # University proposed -> Industry partner must accept/decline
                if not (is_target_industry or is_staff):
                    raise PermissionDenied("Only the invited industry organization partner can accept or decline this engagement.")
        elif action in ['activate', 'complete']:
            # Either active participant (industry partner or university coordinator) or staff can activate/complete
            if not (is_target_industry or is_adopting_coordinator or is_staff):
                raise PermissionDenied("Only participating industry partners or university coordinators can activate or complete this engagement.")

        action_map = {
            'accept': IndustryEngagement.Status.ACCEPTED,
            'decline': IndustryEngagement.Status.DECLINED,
            'activate': IndustryEngagement.Status.ACTIVE,
            'complete': IndustryEngagement.Status.COMPLETED,
        }

        engagement.status = action_map[action]
        if response_notes:
            engagement.response_notes = response_notes

        # Link selected pitch and active project if available
        if not engagement.pitch:
            selected_pitch = Pitch.objects.filter(issue=engagement.issue, status__in=[Pitch.Status.SELECTED, Pitch.Status.MERGED]).first()
            if selected_pitch:
                engagement.pitch = selected_pitch

        if not engagement.project:
            if engagement.pitch and hasattr(engagement.pitch, 'project'):
                engagement.project = engagement.pitch.project
            elif hasattr(engagement.issue, 'projects'):
                engagement.project = engagement.issue.projects.first()

        engagement.save()

        # If accepted or activated, register industry partner in ChallengeCollaborator
        if action in ['accept', 'activate']:
            try:
                ind_users = User.objects.filter(organization=engagement.industry_org, role='industry_partner')
                for ind_user in ind_users:
                    ChallengeCollaborator.objects.get_or_create(
                        issue=engagement.issue,
                        user=ind_user,
                        defaults={
                            'role': ChallengeCollaborator.Role.INDUSTRY_PARTNER,
                            'added_by': request.user,
                            'permissions': {'can_review': True, 'can_advise': True, 'can_sponsor': True}
                        }
                    )
                if getattr(request.user, 'role', '') == 'industry_partner':
                    ChallengeCollaborator.objects.get_or_create(
                        issue=engagement.issue,
                        user=request.user,
                        defaults={
                            'role': ChallengeCollaborator.Role.INDUSTRY_PARTNER,
                            'added_by': request.user,
                            'permissions': {'can_review': True, 'can_advise': True, 'can_sponsor': True}
                        }
                    )
            except Exception:
                pass

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

