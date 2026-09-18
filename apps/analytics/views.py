from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from apps.issues.models import Issue, Adoption
from apps.pitches.models import Pitch, ProjectLifecycle, Project, Certificate
from apps.engagements.models import IndustryEngagement
from apps.users.models import University, Organization, User

class AnalyticsBaseHelper:
    @staticmethod
    def get_lifecycle_metrics():
        # Consistent lifecycle status counting (M-02)
        total_issues = Issue.objects.count()
        validated_issues = Issue.objects.filter(
            status__in=['validated', 'adopted', 'assigned', 'awaiting_verification', 'verified', 'resolved', 'closed']
        ).count()
        adopted_issues = Issue.objects.filter(
            status__in=['adopted', 'assigned', 'awaiting_verification', 'verified', 'resolved', 'closed']
        ).count()
        assigned_issues = Issue.objects.filter(
            status__in=['assigned', 'awaiting_verification', 'verified', 'resolved', 'closed']
        ).count()
        # All completed/terminal resolved states
        resolved_issues = Issue.objects.filter(
            status__in=['resolved', 'verified', 'closed']
        ).count()
        awaiting_verification = Issue.objects.filter(
            status=Issue.Status.AWAITING_VERIFICATION
        ).count()
        escalated_issues = Issue.objects.filter(is_escalated=True).count()

        # Domain/Category distribution
        category_counts = list(
            Issue.objects
            .values('category')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # District-wise distribution
        district_counts = list(
            Issue.objects
            .values('district')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # Institutional participation
        total_universities = University.objects.count()
        active_universities = University.objects.filter(adopted_issues__isnull=False).distinct().count()

        # Student & pitch counts
        total_pitches = Pitch.objects.count()
        selected_pitches = Pitch.objects.filter(status='selected').count()
        merged_pitches = Pitch.objects.filter(status='merged').count()

        # Industry involvement
        total_industry_partners = Organization.objects.count()
        active_engagements = IndustryEngagement.objects.filter(status__in=['accepted', 'active', 'completed']).count()

        # Field Deployment & Citizen confirmation
        field_deployed = Project.objects.filter(
            status__in=[
                Project.Status.DEPLOYED,
                Project.Status.AWAITING_CITIZEN_VERIFICATION,
                Project.Status.VERIFIED,
                Project.Status.CLOSED
            ]
        ).count()
        citizen_confirmed_resolutions = Issue.objects.filter(
            Q(citizen_verified_resolved=True) | Q(status__in=['verified', 'resolved', 'closed'])
        ).count()

        # Real Project Lifecycle model metrics (Issue 32, 33, 54)
        total_projects = Project.objects.count()
        planning_projects = Project.objects.filter(status=Project.Status.PLANNING).count()
        prototype_projects = Project.objects.filter(status=Project.Status.PROTOTYPE).count()
        pilot_projects = Project.objects.filter(status=Project.Status.PILOT).count()
        deployed_projects = Project.objects.filter(status=Project.Status.DEPLOYED).count()
        verified_projects = Project.objects.filter(
            status__in=[Project.Status.VERIFIED, Project.Status.CLOSED]
        ).count()
        total_certificates = Certificate.objects.filter(is_revoked=False).count()

        return {
            'overview': {
                'total_issues_reported': total_issues,
                'validated_issues': validated_issues,
                'adopted_issues': adopted_issues,
                'assigned_solutions': assigned_issues,
                'resolved_issues': resolved_issues,
                'awaiting_verification_issues': awaiting_verification,
                'escalated_unadopted': escalated_issues,
                'total_universities': total_universities,
                'active_participating_universities': active_universities,
                'total_pitches_submitted': total_pitches,
                'selected_solutions': selected_pitches,
                'collaborative_merged_teams': merged_pitches,
                'total_projects': total_projects,
                'projects_planning': planning_projects,
                'projects_prototype': prototype_projects,
                'projects_pilot': pilot_projects,
                'projects_deployed': deployed_projects,
                'projects_verified': verified_projects,
                'verified_outcome_certificates': total_certificates,
                'industry_partners': total_industry_partners,
                'active_industry_partnerships': active_engagements,
                'field_deployments': field_deployed,
                'citizen_confirmed_resolutions': citizen_confirmed_resolutions,
                'is_real_time_aggregate': True,
            },
            'categories': category_counts,
            'districts': district_counts,
        }

    @staticmethod
    def get_institutional_records():
        university_records = []
        for u in University.objects.all():
            adopted_cnt = u.adopted_issues.count()
            resolved_cnt = Issue.objects.filter(
                adoption__university=u,
                status__in=['resolved', 'verified', 'closed']
            ).count()
            projects_cnt = u.projects.count() if hasattr(u, 'projects') else Pitch.objects.filter(university=u, status__in=['selected', 'merged']).count()
            rate = round((resolved_cnt / adopted_cnt) * 100, 1) if adopted_cnt > 0 else 100.0
            university_records.append({
                'id': u.id,
                'name': u.name,
                'district': u.district,
                'code': u.code,
                'adopted_issues_count': adopted_cnt,
                'resolved_issues_count': resolved_cnt,
                'active_projects_count': projects_cnt,
                'resolution_rate': rate,
            })

        industry_records = []
        for org in Organization.objects.all():
            active_cnt = org.engagements.filter(status__in=['accepted', 'active', 'completed']).count()
            industry_records.append({
                'id': org.id,
                'name': org.name,
                'org_type': org.org_type,
                'active_csr_initiatives': active_cnt,
                'total_proposals': org.engagements.count(),
            })

        return {
            'universities': university_records,
            'industry_partners': industry_records,
        }


class GovAnalyticsSummaryView(APIView):
    """
    Analytics summary endpoint (M-02).
    - Public / Unauthenticated callers: Receive public aggregate metrics only.
    - Institutional callers (Gov admin, Coordinator, Mentor, Industry, Staff): Receive full institutional records.
    - Students: 403 Forbidden.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        user = request.user
        if user.is_authenticated and getattr(user, 'role', None) == 'student':
            raise PermissionDenied("Students are not permitted to access Government Analytics.")

        data = AnalyticsBaseHelper.get_lifecycle_metrics()

        # Institutional track record is restricted to authenticated institutional stakeholders
        is_institutional = (
            user.is_authenticated and (
                user.is_staff or
                getattr(user, 'role', None) in ['gov_admin', 'university_coordinator', 'faculty_mentor', 'industry_partner', 'admin']
            )
        )

        if is_institutional:
            data['is_public'] = False
            data['is_institutional'] = True
            data['institutional_track_record'] = AnalyticsBaseHelper.get_institutional_records()
        else:
            data['is_public'] = True
            data['is_institutional'] = False
            data['institutional_track_record'] = {
                'universities': [],
                'industry_partners': []
            }

        return Response(data)


class InstitutionalAnalyticsView(APIView):
    """
    Dedicated authenticated institutional analytics endpoint (M-02).
    Restricted to institutional stakeholders and administrators.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        allowed_roles = ['gov_admin', 'university_coordinator', 'faculty_mentor', 'industry_partner', 'admin']
        if not (user.is_staff or getattr(user, 'role', None) in allowed_roles):
            raise PermissionDenied("Access to institutional analytics is restricted to university, industry, and government leaders.")

        data = AnalyticsBaseHelper.get_lifecycle_metrics()
        data['institutional_track_record'] = AnalyticsBaseHelper.get_institutional_records()
        return Response(data)


class AuditLogsAnalyticsView(APIView):
    """
    Live Administrative Audit Trail and telemetry stream.
    Queries database AuditLog and ActivityEvent records.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', None) in ['admin', 'gov_admin']
        if not is_admin:
            raise PermissionDenied("Only administrators can view the audit stream.")

        from apps.users.models import AuditLog
        from apps.issues.models import ActivityEvent

        logs = []
        # 1. Fetch AuditLog records
        for log in AuditLog.objects.select_related('actor').all()[:50]:
            logs.append({
                'id': f"audit-{log.id}",
                'time': log.created_at.isoformat(),
                'event': f"[{log.action.upper()}] {log.entity_type} #{log.entity_id} - Actor: {log.actor.name if log.actor else 'System'}",
                'level': 'AUDIT',
                'ip': log.ip_address or '127.0.0.1 (API Gateway)',
            })

        # 2. Fetch ActivityEvents
        for event in ActivityEvent.objects.select_related('actor', 'issue').all()[:50]:
            logs.append({
                'id': f"activity-{event.id}",
                'time': event.created_at.isoformat(),
                'event': f"[{event.event_type}] Issue #{event.issue_id} ({event.issue.title[:30]}): {event.description}",
                'level': 'ACTIVITY',
                'ip': '127.0.0.1 (Core Gateway)',
            })

        # Sort by timestamp descending
        logs.sort(key=lambda x: x['time'], reverse=True)

        return Response(logs[:50])


