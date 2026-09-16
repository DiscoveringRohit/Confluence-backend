from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from apps.issues.models import Issue, Adoption
from apps.pitches.models import Pitch, ProjectLifecycle, Project, Certificate
from apps.engagements.models import IndustryEngagement
from apps.users.models import University, Organization, User

class GovAnalyticsSummaryView(APIView):
    """
    Returns aggregate statistics for government administrators,
    institutional leaders, and the public dashboard summary.
    Excludes all confidential and raw pitch details.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if request.user.is_authenticated and request.user.role == 'student':
            raise PermissionDenied("Students are not permitted to access Government Analytics.")

        total_issues = Issue.objects.count()
        validated_issues = Issue.objects.filter(status__in=['validated', 'adopted', 'assigned', 'resolved']).count()
        adopted_issues = Issue.objects.filter(status__in=['adopted', 'assigned', 'resolved']).count()
        assigned_issues = Issue.objects.filter(status__in=['assigned', 'resolved']).count()
        resolved_issues = Issue.objects.filter(status='resolved').count()
        escalated_issues = Issue.objects.filter(is_escalated=True).count()

        # Domain/Category distribution
        category_counts = (
            Issue.objects
            .values('category')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # District-wise distribution
        district_counts = (
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
        field_deployed = Project.objects.filter(status__in=[Project.Status.DEPLOYED, Project.Status.VERIFIED]).count() or ProjectLifecycle.objects.filter(outcome_status='deployed').count()
        citizen_confirmed_resolutions = Issue.objects.filter(citizen_verified_resolved=True).count()

        # Real Project Lifecycle model metrics (Issue 32, 33, 54)
        total_projects = Project.objects.count()
        planning_projects = Project.objects.filter(status=Project.Status.PLANNING).count()
        prototype_projects = Project.objects.filter(status=Project.Status.PROTOTYPE).count()
        pilot_projects = Project.objects.filter(status=Project.Status.PILOT).count()
        verified_projects = Project.objects.filter(status=Project.Status.VERIFIED).count()
        total_certificates = Certificate.objects.filter(is_revoked=False).count()

        # Institutional Track Record calculations
        university_records = []
        for u in University.objects.all():
            adopted_cnt = u.adopted_issues.count()
            resolved_cnt = Issue.objects.filter(adoption__university=u, status='resolved').count()
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

        return Response({
            'overview': {
                'total_issues_reported': total_issues,
                'validated_issues': validated_issues,
                'adopted_issues': adopted_issues,
                'assigned_solutions': assigned_issues,
                'resolved_issues': resolved_issues,
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
                'projects_verified': verified_projects,
                'verified_outcome_certificates': total_certificates,
                'industry_partners': total_industry_partners,
                'active_industry_partnerships': active_engagements,
                'field_deployments': field_deployed,
                'citizen_confirmed_resolutions': citizen_confirmed_resolutions,
                'is_real_time_aggregate': True,
            },
            'categories': list(category_counts),
            'districts': list(district_counts),
            'institutional_track_record': {
                'universities': university_records,
                'industry_partners': industry_records,
            },
        })

