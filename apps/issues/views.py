import requests
from django.db import models
from django.utils import timezone
from django.conf import settings
from rest_framework import generics, permissions, status, filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (
    Issue, Adoption, StudentNomination, IssueStatusHistory,
    OpenCall, CitizenVerification, ActivityEvent, DiscussionComment,
    ChallengeCollaborator, log_activity
)
from .permissions import CanUpdateIssue
from .serializers import (
    IssueSerializer,
    IssueModerationSerializer,
    AdoptionSerializer,
    StudentNominationSerializer,
    OpenCallSerializer,
    CitizenVerificationSerializer,
    ActivityEventSerializer,
    DiscussionCommentSerializer,
    IssueStatusHistorySerializer,
    ChallengeCollaboratorSerializer,
)
from apps.notifications.models import Notification
from apps.users.permissions import (
    IsCitizen,
    IsStudent,
    IsUniversityCoordinator,
    IsGovAdmin,
)

def run_ai_triage(issue):
    """
    Attempt to invoke the AI microservice for classification and deduplication.
    Falls back gracefully if the microservice is offline or still starting up.
    """
    try:
        url = f"{settings.AI_SERVICE_URL}/triage"
        # Pass existing issues to enable cross-district/district similarity-based duplicate detection
        existing_issues = list(
            Issue.objects.exclude(id=issue.id)
            .values('id', 'title', 'description', 'district')[:50]
        )
        payload = {
            "title": issue.title,
            "description": issue.description,
            "district": issue.district,
            "existing_issues": existing_issues,
        }
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            data = res.json()
            issue.category = data.get('predicted_category', issue.category)
            issue.ai_confidence = data.get('confidence', 0.85)
            issue.ai_triage_notes = data.get('summary', 'AI classification applied')
            update_fields = ['category', 'ai_confidence', 'ai_triage_notes']
            if data.get('potential_duplicate_id'):
                try:
                    dup = Issue.objects.get(id=data['potential_duplicate_id'])
                    issue.duplicate_of = dup
                    issue.ai_triage_notes += f" | Flagged duplicate of #{dup.id}"
                    update_fields.append('duplicate_of')
                except Issue.DoesNotExist:
                    pass
            issue.save(update_fields=update_fields)
            return
    except Exception:
        pass

    # 2. Direct Gemini Multimodal Vision & Triage with Key Rotation
    try:
        from .gemini_service import call_gemini_triage
        photo_path = None
        if issue.photo and hasattr(issue.photo, 'path'):
            photo_path = issue.photo.path

        gemini_result = call_gemini_triage(
            title=issue.title,
            description=issue.description,
            district=issue.district,
            photo_path=photo_path,
            photo_url=issue.photo_url
        )
        if gemini_result:
            issue.category = gemini_result.get('category', issue.category)
            issue.ai_confidence = float(gemini_result.get('confidence_score', 0.92))
            key_used = gemini_result.get('key_used', 'Gemini')
            notes = gemini_result.get('verification_notes', 'Verified via Gemini Multimodal Vision')
            issue.ai_triage_notes = f"[Gemini 3.6 Flash | {key_used}] {notes}"
            issue.save(update_fields=['category', 'ai_confidence', 'ai_triage_notes'])
            return
    except Exception as e:
        logger.warning("Gemini direct triage failed: %s", e)

    # 3. Rule-based heuristic fallback if AI services are unavailable
    desc_lower = (issue.title + " " + issue.description).lower()
    if any(k in desc_lower for k in ['school', 'teacher', 'student', 'book', 'class', 'college']):
        issue.category = Issue.Category.EDUCATION
    elif any(k in desc_lower for k in ['water', 'pipe', 'leak', 'drain', 'contamination', 'borewell']):
        issue.category = Issue.Category.WATER
    elif any(k in desc_lower for k in ['crop', 'farmer', 'soil', 'irrigation', 'harvest', 'paddy', 'seed']):
        issue.category = Issue.Category.AGRICULTURE
    elif any(k in desc_lower for k in ['hospital', 'doctor', 'clinic', 'medicine', 'health', 'disease', 'phc']):
        issue.category = Issue.Category.HEALTHCARE
    elif any(k in desc_lower for k in ['road', 'bridge', 'pothole', 'traffic', 'light', 'garbage', 'drainage']):
        issue.category = Issue.Category.URBAN_INFRA
    elif any(k in desc_lower for k in ['forest', 'tree', 'pollution', 'mine', 'coal', 'river', 'smoke']):
        issue.category = Issue.Category.ENVIRONMENT
    elif any(k in desc_lower for k in ['solar', 'power', 'electric', 'grid', 'transformer']):
        issue.category = Issue.Category.ENERGY
    else:
        issue.category = Issue.Category.RURAL_LIVELIHOODS

    issue.ai_confidence = 0.80
    issue.ai_triage_notes = "Auto-triaged by rule-based heuristic"
    issue.save(update_fields=['category', 'ai_confidence', 'ai_triage_notes'])


def get_issue_by_pk_or_public_id(pk):
    """Resolve an issue/challenge by either its primary key or public_id (e.g. CH-00042)."""
    if pk is None:
        return None
    if str(pk).isdigit():
        return Issue.objects.filter(models.Q(pk=int(pk)) | models.Q(public_id=str(pk))).first()
    return Issue.objects.filter(public_id=str(pk)).first()


class IssueListCreateView(generics.ListCreateAPIView):
    serializer_class = IssueSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['public_id', 'title', 'description', 'district', 'address']
    throttle_scope = 'issue_create'

    def get_throttles(self):
        if self.request.method.lower() == 'post':
            return super().get_throttles()
        return []

    def get_queryset(self):
        qs = Issue.objects.select_related('submitted_by', 'adoption', 'adoption__university', 'duplicate_of').all().order_by('-created_at')
        
        status_param = self.request.query_params.get('status')
        status_in_param = self.request.query_params.get('status__in')
        category_param = self.request.query_params.get('category')
        district_param = self.request.query_params.get('district')
        mine_param = self.request.query_params.get('mine')

        if status_param:
            if ',' in status_param:
                qs = qs.filter(status__in=[s.strip() for s in status_param.split(',') if s.strip()])
            else:
                qs = qs.filter(status=status_param)
        elif status_in_param:
            qs = qs.filter(status__in=[s.strip() for s in status_in_param.split(',') if s.strip()])

        if category_param:
            qs = qs.filter(category=category_param)
        if district_param:
            qs = qs.filter(district__iexact=district_param)
        if mine_param and self.request.user.is_authenticated:
            qs = qs.filter(submitted_by=self.request.user)

        # Unauthenticated users or regular citizens on public board see validated, adopted, assigned, resolved
        if not self.request.user.is_authenticated or self.request.user.role == 'citizen':
            if not mine_param:
                qs = qs.exclude(status=Issue.Status.SUBMITTED)

        return qs

    def perform_create(self, serializer):
        issue = serializer.save(submitted_by=self.request.user)
        IssueStatusHistory.objects.create(
            issue=issue,
            previous_status='',
            new_status=issue.status,
            actor=self.request.user,
            reason='Initial citizen submission'
        )
        ChallengeCollaborator.objects.get_or_create(
            issue=issue,
            user=self.request.user,
            defaults={'role': ChallengeCollaborator.Role.CITIZEN_CONTRIBUTOR}
        )
        run_ai_triage(issue)


class IssueDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Issue.objects.select_related('submitted_by', 'adoption', 'adoption__university').prefetch_related('status_history').all()
    serializer_class = IssueSerializer
    permission_classes = [CanUpdateIssue]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        pk = self.kwargs.get('pk')
        queryset = self.filter_queryset(self.get_queryset())
        if str(pk).isdigit():
            obj = queryset.filter(models.Q(pk=int(pk)) | models.Q(public_id=str(pk))).first()
        else:
            obj = queryset.filter(public_id=str(pk)).first()
        if not obj:
            from rest_framework.exceptions import NotFound
            raise NotFound("Challenge not found.")
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_update(self, serializer):
        user = self.request.user
        old_status = self.get_object().status
        requested_status = serializer.validated_data.get('status')
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', None) in ['gov_admin', 'admin']
        if requested_status and requested_status != old_status and not is_admin:
            raise ValidationError({'status': 'Challenge status cannot be modified via direct update. Use canonical lifecycle workflow endpoints.'})

        # Field-level restrictions (Issue 47)
        if getattr(user, 'role', None) == 'citizen' and not user.is_staff:
            disallowed = {'status', 'validated_by', 'maintaining_university', 'managed_by'}
            for f in disallowed:
                if f in serializer.validated_data:
                    serializer.validated_data.pop(f)

        instance = serializer.save()
        if instance.status != old_status:
            IssueStatusHistory.objects.create(
                issue=instance,
                previous_status=old_status,
                new_status=instance.status,
                actor=self.request.user,
                reason=f'Status updated by {user.name or user.email}'
            )


class AdminForceAdoptView(APIView):
    """
    Omnipotent Admin Endpoint:
    Force-adopt any challenge to any university with zero restrictions, bypassing normal nominations or waiting periods.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', None) in ['admin', 'gov_admin']
        if not is_admin:
            raise PermissionDenied("Only administrators can force-adopt challenges.")

        issue = get_issue_by_pk_or_public_id(pk)
        if not issue:
            return Response({'error': 'Challenge not found'}, status=status.HTTP_404_NOT_FOUND)

        university_id = request.data.get('university_id')
        if not university_id:
            return Response({'error': 'university_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        university = University.objects.filter(id=university_id).first()
        if not university:
            return Response({'error': 'University not found'}, status=status.HTTP_404_NOT_FOUND)

        issue.maintaining_university = university
        issue.save(update_fields=['maintaining_university'])

        adoption, _ = Adoption.objects.update_or_create(
            issue=issue,
            defaults={
                'university': university,
                'coordinator': user,
                'status': Adoption.Status.APPROVED,
                'mode': Adoption.Mode.SELF_ADOPTED,
            }
        )

        old_status = issue.status
        issue.status = Issue.Status.ADOPTED
        issue.save(update_fields=['status'])

        if old_status != Issue.Status.ADOPTED:
            IssueStatusHistory.objects.create(
                issue=issue,
                previous_status=old_status,
                new_status=Issue.Status.ADOPTED,
                actor=user,
                reason=f'Force-adopted by Administrator to {university.name}'
            )

        log_activity(
            issue=issue,
            actor=user,
            event_type='force_adopted',
            description=f'Admin force-adopted challenge to {university.name}'
        )

        return Response(IssueSerializer(issue, context={'request': request}).data, status=status.HTTP_200_OK)


class IssueModerationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        allowed_roles = {'gov_admin', 'admin'}
        if getattr(request.user, 'role', None) not in allowed_roles and not request.user.is_staff and not request.user.is_superuser:
            raise PermissionDenied("Only government moderators or platform administrators can moderate issues.")

        issue = get_issue_by_pk_or_public_id(pk)
        if not issue:
            return Response({'error': 'Issue not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = IssueModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']

        if action == 'validate':
            update_fields = ['validated_by']
            issue.validated_by = request.user
            if 'category' in serializer.validated_data:
                issue.category = serializer.validated_data['category']
                update_fields.append('category')
            issue.save(update_fields=update_fields)
            collab_role = ChallengeCollaborator.Role.COORDINATOR if getattr(request.user, 'role', None) in ['university_coordinator', 'faculty_mentor'] else ChallengeCollaborator.Role.GOVERNMENT
            ChallengeCollaborator.objects.get_or_create(
                issue=issue,
                user=request.user,
                defaults={'role': collab_role}
            )
            issue.transition_status(
                Issue.Status.VALIDATED,
                actor=request.user,
                reason=serializer.validated_data.get('notes', 'Issue validated and approved for university open calls.')
            )
            return Response({'message': 'Issue validated and approved for university open calls.', 'status': issue.status})

        elif action == 'reject':
            issue.transition_status(
                Issue.Status.REJECTED,
                actor=request.user,
                reason=serializer.validated_data.get('notes', 'Issue rejected by moderator.')
            )
            return Response({'message': 'Issue rejected.', 'status': issue.status})

        elif action == 'mark_duplicate':
            dup_id = serializer.validated_data.get('duplicate_of_id')
            if not dup_id:
                return Response({'error': 'duplicate_of_id required'}, status=status.HTTP_400_BAD_REQUEST)
            parent = get_issue_by_pk_or_public_id(dup_id)
            if not parent:
                return Response({'error': 'Target duplicate issue does not exist'}, status=status.HTTP_404_NOT_FOUND)
            issue.duplicate_of = parent
            issue.transition_status(
                Issue.Status.DUPLICATE,
                actor=request.user,
                reason=f'Marked as duplicate of #{parent.id}'
            )
            return Response({'message': f'Issue marked as duplicate of #{parent.id}'})


class AdoptIssueView(APIView):
    """
    University coordinator adopts a validated issue directly.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        allowed_roles = {'university_coordinator', 'gov_admin', 'admin'}
        if getattr(request.user, 'role', None) not in allowed_roles and not request.user.is_staff and not request.user.is_superuser:
            raise PermissionDenied("Only university coordinators or administrators can adopt issues.")

        issue = get_issue_by_pk_or_public_id(pk)
        if not issue:
            return Response({'error': 'Issue not found'}, status=status.HTTP_404_NOT_FOUND)

        if issue.status not in [Issue.Status.VALIDATED, Issue.Status.SUBMITTED]:
            return Response({'error': f'Issue cannot be adopted because status is {issue.status}'}, status=status.HTTP_400_BAD_REQUEST)

        if issue.status == Issue.Status.SUBMITTED:
            issue.transition_status(
                Issue.Status.VALIDATED,
                actor=request.user,
                reason="Auto-validated upon adoption"
            )

        university = getattr(request.user, 'university', None)
        if not university:
            return Response(
                {'error': 'User must have an active university affiliation to adopt an issue.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if hasattr(issue, 'adoption'):
            return Response({'error': 'Issue is already adopted.'}, status=status.HTTP_400_BAD_REQUEST)

        adoption = Adoption.objects.create(
            issue=issue,
            university=university,
            coordinator=request.user,
            mode=Adoption.Mode.SELF_ADOPTED
        )
        issue.maintaining_university = university
        issue.managed_by = request.user
        issue.save(update_fields=['maintaining_university', 'managed_by'])
        ChallengeCollaborator.objects.get_or_create(
            issue=issue,
            user=request.user,
            defaults={'role': ChallengeCollaborator.Role.COORDINATOR}
        )
        issue.transition_status(
            Issue.Status.ADOPTED,
            actor=request.user,
            reason=f'Adopted by {university.name}'
        )

        return Response(AdoptionSerializer(adoption).data, status=status.HTTP_201_CREATED)


class NominateIssueView(APIView):
    """
    Student nominates an unclaimed issue for their university to adopt.
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request, pk):
        issue = get_issue_by_pk_or_public_id(pk)
        if not issue:
            return Response({'error': 'Issue not found'}, status=status.HTTP_404_NOT_FOUND)

        university = request.user.university
        if not university:
            return Response({'error': 'Student must be affiliated with a university.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if already adopted by student's university
        if hasattr(issue, 'adoption') and issue.adoption.university_id == university.id and getattr(issue.adoption, 'status', None) == 'approved':
            return Response({'error': 'This challenge is already adopted by your university. Students can write pitches directly.'}, status=status.HTTP_400_BAD_REQUEST)

        # Disallow if already adopted by another university
        if hasattr(issue, 'adoption') and getattr(issue.adoption, 'status', None) == 'approved' and issue.adoption.university_id != university.id:
            return Response({'error': f'This challenge has already been adopted by {issue.adoption.university.name}.'}, status=status.HTTP_400_BAD_REQUEST)

        # Disallow terminal or closed states
        if issue.status in [Issue.Status.RESOLVED, Issue.Status.REJECTED, Issue.Status.DUPLICATE]:
            return Response({'error': f'Cannot nominate an issue with status {issue.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        rationale = request.data.get('rationale', '')
        nomination, created = StudentNomination.objects.get_or_create(
            issue=issue,
            university=university,
            student=request.user,
            defaults={'rationale': rationale}
        )
        if not created:
            return Response({'message': 'You have already nominated this issue.'}, status=status.HTTP_200_OK)

        return Response(StudentNominationSerializer(nomination).data, status=status.HTTP_201_CREATED)


class ReviewNominationView(APIView):
    """
    University coordinator approves or rejects a student's nomination.
    Approving creates the official Adoption and marks the issue as adopted (Open Call).
    """
    permission_classes = [permissions.IsAuthenticated, IsUniversityCoordinator]

    def post(self, request, pk):
        try:
            nomination = StudentNomination.objects.get(pk=pk, university=request.user.university)
        except StudentNomination.DoesNotExist:
            return Response({'error': 'Nomination not found for your university.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        if action not in ['approve', 'reject']:
            return Response({'error': 'Action must be approve or reject'}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'approve':
            nomination.status = StudentNomination.Status.APPROVED
            nomination.reviewed_at = timezone.now()
            nomination.save()

            issue = nomination.issue
            # Convert to official adoption
            adoption, _ = Adoption.objects.get_or_create(
                issue=issue,
                defaults={
                    'university': nomination.university,
                    'coordinator': request.user,
                    'mode': Adoption.Mode.NOMINATION_APPROVED,
                    'nominated_by': nomination.student
                }
            )
            issue.maintaining_university = nomination.university
            issue.managed_by = request.user
            issue.save(update_fields=['maintaining_university', 'managed_by'])
            ChallengeCollaborator.objects.get_or_create(
                issue=issue,
                user=request.user,
                defaults={'role': ChallengeCollaborator.Role.COORDINATOR}
            )
            ChallengeCollaborator.objects.get_or_create(
                issue=issue,
                user=nomination.student,
                defaults={'role': ChallengeCollaborator.Role.STUDENT_CONTRIBUTOR}
            )
            issue.transition_status(
                Issue.Status.ADOPTED,
                actor=request.user,
                reason=f'Student nomination approved by {nomination.university.name}'
            )

            return Response({
                'message': 'Nomination approved! Issue is now adopted by university and open for pitches.',
                'adoption': AdoptionSerializer(adoption).data
            })
        else:
            nomination.status = StudentNomination.Status.REJECTED
            nomination.reviewed_at = timezone.now()
            nomination.save()
            return Response({'message': 'Nomination rejected.'})


class UniversityNominationsListView(generics.ListAPIView):
    """
    List nominations.
    - If user is a student: returns nominations submitted by the student.
    - If user is coordinator/mentor: returns pending nominations received by their university.
    """
    serializer_class = StudentNominationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', None) == 'student':
            return StudentNomination.objects.filter(
                student=user
            ).order_by('-created_at')

        return StudentNomination.objects.filter(
            university=user.university,
            status=StudentNomination.Status.PENDING
        ).order_by('-created_at')


class CitizenConfirmResolutionView(APIView):
    """
    Close the loop with the citizen: lets the original submitter confirm whether
    the deployed solution resolved the societal issue.
    Creates a CitizenVerification record, transitions issue & project states, and logs an ActivityEvent (P0 Issue 10 & P1 Issue 36-37).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        issue = get_issue_by_pk_or_public_id(pk)
        if not issue:
            return Response({'error': 'Issue not found'}, status=status.HTTP_404_NOT_FOUND)

        if issue.submitted_by != request.user and not request.user.is_staff and getattr(request.user, 'role', '') != 'gov_admin':
            raise PermissionDenied("Only the original citizen submitter or administrative authority can confirm resolution.")

        # Issue 36: Citizen verification requires implementation/deployment stage (cannot verify submitted/validating/adopted issues before solution/project assignment)
        if issue.status in [Issue.Status.SUBMITTED, Issue.Status.VALIDATING, Issue.Status.VALIDATED, Issue.Status.ADOPTED]:
            return Response(
                {'error': f"Cannot verify resolution for a challenge in '{issue.status}' status. Challenge must be deployed or awaiting verification."},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_confirmed = request.data.get('confirmed', True)
        if isinstance(is_confirmed, str):
            is_confirmed = is_confirmed.lower() in ['true', '1', 'yes']

        feedback = request.data.get('feedback', '')
        reason = request.data.get('reason', '') or feedback
        what_is_still_wrong = request.data.get('what_is_still_wrong', '')
        evidence = request.data.get('evidence', '')
        photo_video_url = request.data.get('photo_video_url', '')

        # Issue 37: Mandatory reason & explanation when citizen reports not resolved
        if not is_confirmed and not reason.strip() and not what_is_still_wrong.strip():
            return Response(
                {'error': 'Reason or explanation of what is still wrong is required when reporting challenge as not resolved.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        issue.citizen_verified_resolved = is_confirmed
        issue.citizen_feedback_on_resolution = what_is_still_wrong or reason or feedback
        issue.save(update_fields=['citizen_verified_resolved', 'citizen_feedback_on_resolution'])

        result_choice = CitizenVerification.Result.VERIFIED if is_confirmed else CitizenVerification.Result.NOT_RESOLVED
        verification = CitizenVerification.objects.create(
            issue=issue,
            citizen=request.user,
            result=result_choice,
            reason=reason,
            what_is_still_wrong=what_is_still_wrong,
            evidence=evidence,
            photo_video_url=photo_video_url
        )

        log_activity(
            issue=issue,
            actor=request.user,
            event_type='citizen_verification',
            description=f"Citizen {'verified resolution' if is_confirmed else 'reported problem as not resolved: ' + (what_is_still_wrong or reason)}",
            object_type='citizen_verification',
            object_id=verification.id,
            metadata={
                'result': result_choice,
                'feedback': feedback,
                'reason': reason,
                'what_is_still_wrong': what_is_still_wrong,
                'photo_video_url': photo_video_url
            }
        )

        if is_confirmed:
            issue.transition_status(
                Issue.Status.RESOLVED,
                actor=request.user,
                reason=feedback or reason or 'Citizen confirmed resolution in the field.'
            )
            for proj in issue.projects.all():
                try:
                    proj.transition_status(proj.Status.VERIFIED, actor=request.user, reason="Citizen verified resolution in the field.")
                except Exception:
                    pass
        else:
            reopen_reason = what_is_still_wrong or reason or 'Citizen reported problem is NOT resolved. Reopened for team investigation.'
            issue.transition_status(
                Issue.Status.REOPENED,
                actor=request.user,
                reason=reopen_reason
            )
            for proj in issue.projects.all():
                try:
                    proj.transition_status(proj.Status.REOPENED, actor=request.user, reason=reopen_reason)
                except Exception:
                    pass

            # Issue 37: Dispatch action notifications to university coordinator and project team
            try:
                if hasattr(issue, 'adoption') and issue.adoption and issue.adoption.coordinator:
                    Notification.objects.create(
                        recipient=issue.adoption.coordinator,
                        title=f"Action Required: Challenge #{issue.id} Reopened by Citizen",
                        message=f"Citizen reported problem is not resolved for '{issue.title}'. Details: {reopen_reason}",
                        notification_type=Notification.NotificationType.ISSUE,
                        link_url=f"/university/challenges/{issue.id}"
                    )
                for proj in issue.projects.all():
                    if proj.mentor:
                        Notification.objects.create(
                            recipient=proj.mentor,
                            title=f"Action Required: Project #{proj.id} Reopened by Citizen",
                            message=f"Citizen reported problem is not resolved for '{issue.title}'. Details: {reopen_reason}",
                            notification_type=Notification.NotificationType.PROJECT,
                            link_url=f"/projects/{proj.id}"
                        )
                    for member in proj.team.all():
                        Notification.objects.create(
                            recipient=member,
                            title=f"Action Required: Field Resolution Rejected by Citizen",
                            message=f"Citizen reported problem is not resolved for '{issue.title}'. Details: {reopen_reason}",
                            notification_type=Notification.NotificationType.PROJECT,
                            link_url=f"/projects/{proj.id}"
                        )
            except Exception:
                pass

        return Response({
            'message': 'Citizen resolution feedback recorded.',
            'status': issue.status,
            'citizen_verified_resolved': issue.citizen_verified_resolved,
            'citizen_feedback_on_resolution': issue.citizen_feedback_on_resolution,
            'verification': CitizenVerificationSerializer(verification).data
        })


class OpenCallListCreateView(generics.ListCreateAPIView):
    """
    List open calls across all challenges or filter by issue / university.
    POST creates an Open Call for an adopted challenge (Coordinator only).
    """
    serializer_class = OpenCallSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = None
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'required_skills', 'departments']
    ordering_fields = ['opening_date', 'closing_date', 'created_at']

    def get_queryset(self):
        qs = OpenCall.objects.all().select_related('issue', 'university', 'created_by')
        issue_id = self.request.query_params.get('issue')
        if issue_id:
            qs = qs.filter(issue_id=issue_id)
        univ_id = self.request.query_params.get('university')
        if univ_id:
            qs = qs.filter(university_id=univ_id)
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated or getattr(user, 'role', None) != 'university_coordinator':
            raise PermissionDenied("Only university coordinators can create Open Calls.")

        issue = serializer.validated_data['issue']
        university = getattr(user, 'university', None)
        if not university:
            raise ValidationError({'university': 'User is not associated with a university.'})

        if not hasattr(issue, 'adoption') or issue.adoption.university != university:
            raise PermissionDenied("Your university has not adopted this challenge.")

        open_call = serializer.save(university=university, created_by=user)
        log_activity(
            issue=issue,
            actor=user,
            event_type='open_call_created',
            description=f"Open call '{open_call.title}' launched by {university.name}",
            object_type='open_call',
            object_id=open_call.id,
            metadata={'open_call_title': open_call.title, 'closing_date': str(open_call.closing_date)}
        )


class OpenCallDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or cancel an Open Call.
    Only the university coordinator who created it can edit it.
    """
    queryset = OpenCall.objects.all()
    serializer_class = OpenCallSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if getattr(user, 'role', None) != 'university_coordinator' or instance.university != getattr(user, 'university', None):
            raise PermissionDenied("Only the adopting university coordinator can update this Open Call.")
        open_call = serializer.save()
        log_activity(
            issue=open_call.issue,
            actor=user,
            event_type='open_call_updated',
            description=f"Open call '{open_call.title}' was updated.",
            object_type='open_call',
            object_id=open_call.id
        )


class IssueActivityTimelineView(generics.ListAPIView):
    """
    Chronological activity timeline for an issue (P0 Issue 8 & P1 Issue 38).
    Supports query parameter filters: event_type, object_type, actor_id.
    """
    serializer_class = ActivityEventSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        pk = self.kwargs.get('pk')
        issue = get_issue_by_pk_or_public_id(pk)
        issue_id = issue.id if issue else None
        qs = ActivityEvent.objects.filter(issue_id=issue_id).select_related('actor').order_by('-created_at')

        event_type = self.request.query_params.get('event_type')
        if event_type:
            qs = qs.filter(event_type__iexact=event_type)

        object_type = self.request.query_params.get('object_type')
        if object_type:
            qs = qs.filter(object_type__iexact=object_type)

        actor_id = self.request.query_params.get('actor_id')
        if actor_id:
            qs = qs.filter(actor_id=actor_id)

        return qs


class IssueStatusHistoryView(generics.ListAPIView):
    """
    Status transition audit log for a challenge repository (P1 Issue 39).
    Returns complete chronological transition history.
    """
    serializer_class = IssueStatusHistorySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        pk = self.kwargs.get('pk')
        issue = get_issue_by_pk_or_public_id(pk)
        issue_id = issue.id if issue else None
        return IssueStatusHistory.objects.filter(issue_id=issue_id).select_related('actor').order_by('-created_at')


class IssueDiscussionListCreateView(generics.ListCreateAPIView):
    """
    Challenge-level repository discussions (Section 40 & P1 Issue 18 & 40).
    Citizens, students, mentors, and coordinators can discuss problem clarification, requirements, and constraints.
    """
    serializer_class = DiscussionCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        issue_id = self.kwargs.get('issue_id')
        issue = get_issue_by_pk_or_public_id(issue_id)
        resolved_id = issue.id if issue else None
        qs = DiscussionComment.objects.filter(
            issue_id=resolved_id,
            target_type='challenge'
        ).select_related('author').order_by('created_at')
        cat = self.request.query_params.get('category')
        if cat:
            qs = qs.filter(category=cat.lower())
        return qs

    def perform_create(self, serializer):
        issue_id = self.kwargs.get('issue_id')
        issue = get_issue_by_pk_or_public_id(issue_id)
        if not issue:
            raise ValidationError({'issue': 'Issue does not exist.'})

        cat = self.request.data.get('category', 'general')
        comment = serializer.save(
            author=self.request.user,
            issue=issue,
            target_type='challenge',
            category=cat
        )

        try:
            log_activity(
                issue=issue,
                actor=self.request.user,
                event_type='CHALLENGE_DISCUSSION',
                description=f"{self.request.user.name or self.request.user.email} commented on Challenge #{issue.id}: {comment.content[:50]}",
                object_type='discussion',
                object_id=str(comment.id)
            )
        except Exception:
            pass


class ChallengeCollaboratorListCreateView(generics.ListCreateAPIView):
    """
    Challenge collaborators and repository-style role management (Section 43).
    Supports roles: maintainer, coordinator, faculty, student_contributor, government, industry_partner, citizen_contributor.
    """
    serializer_class = ChallengeCollaboratorSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        issue_id = self.kwargs.get('issue_id')
        issue = get_issue_by_pk_or_public_id(issue_id)
        resolved_id = issue.id if issue else None
        return ChallengeCollaborator.objects.filter(issue_id=resolved_id).select_related('user', 'added_by').order_by('created_at')

    def create(self, request, *args, **kwargs):
        issue_id = self.kwargs.get('issue_id')
        issue = get_issue_by_pk_or_public_id(issue_id)
        if not issue:
            raise ValidationError({'issue': 'Issue does not exist.'})

        # Permission check: Coordinator of maintaining university, managed_by user, staff/admin, or existing coordinator collaborator
        user = self.request.user
        is_authorized = (
            user.is_staff or
            user.is_superuser or
            (issue.managed_by_id and issue.managed_by_id == user.id) or
            (issue.maintaining_university_id and getattr(user, 'university_id', None) == issue.maintaining_university_id and getattr(user, 'role', '') == 'university_coordinator') or
            (hasattr(issue, 'adoption') and issue.adoption and issue.adoption.coordinator_id == user.id) or
            ChallengeCollaborator.objects.filter(issue=issue, user=user, role__in=[ChallengeCollaborator.Role.MAINTAINER, ChallengeCollaborator.Role.COORDINATOR]).exists()
        )
        if not is_authorized:
            raise PermissionDenied("Only the managing university coordinator or maintainer can add collaborators to this challenge repository.")

        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        issue_id = self.kwargs.get('issue_id')
        issue = get_issue_by_pk_or_public_id(issue_id)
        if not issue:
            raise ValidationError({'issue': 'Issue does not exist.'})
        collaborator = serializer.save(
            issue=issue,
            added_by=self.request.user
        )

        log_activity(
            issue=issue,
            actor=self.request.user,
            event_type='COLLABORATOR_ADDED',
            description=f"{self.request.user.name or self.request.user.email} added {collaborator.user.name or collaborator.user.email} as {collaborator.get_role_display()}",
            object_type='collaborator',
            object_id=str(collaborator.id),
            metadata={'collaborator_id': collaborator.id, 'role': collaborator.role, 'user_id': collaborator.user_id}
        )


class ChallengeCollaboratorDetailView(generics.DestroyAPIView):
    """
    Remove a challenge collaborator (Section 43).
    """
    serializer_class = ChallengeCollaboratorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        issue_id = self.kwargs.get('issue_id')
        return ChallengeCollaborator.objects.filter(issue_id=issue_id)

    def perform_destroy(self, instance):
        issue = instance.issue
        user = self.request.user
        is_authorized = (
            user.is_staff or
            user.is_superuser or
            (issue.managed_by_id and issue.managed_by_id == user.id) or
            (issue.maintaining_university_id and getattr(user, 'university_id', None) == issue.maintaining_university_id and getattr(user, 'role', '') == 'university_coordinator') or
            (hasattr(issue, 'adoption') and issue.adoption and issue.adoption.coordinator_id == user.id) or
            ChallengeCollaborator.objects.filter(issue=issue, user=user, role__in=[ChallengeCollaborator.Role.MAINTAINER, ChallengeCollaborator.Role.COORDINATOR]).exists()
        )
        if not is_authorized:
            raise PermissionDenied("Only the managing coordinator or maintainer can remove collaborators.")

        log_activity(
            issue=issue,
            actor=self.request.user,
            event_type='COLLABORATOR_REMOVED',
            description=f"{self.request.user.name or self.request.user.email} removed collaborator {instance.user.name or instance.user.email} ({instance.get_role_display()})",
            object_type='collaborator',
            object_id=str(instance.id)
        )
        instance.delete()


class StatusContractView(APIView):
    """
    Machine-readable canonical status contract & state machine schemas (Section 45).
    Exposes canonical state machines, flows, terminal statuses, and topics across Challenge, Solution, Project, Milestones.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from apps.pitches.models import Pitch, Project, ProjectMilestone

        return Response({
            'version': '1.0.0',
            'challenges': {
                'statuses': dict(Issue.Status.choices),
                'canonical_flow': [
                    Issue.Status.SUBMITTED,
                    Issue.Status.VALIDATING,
                    Issue.Status.VALIDATED,
                    Issue.Status.ADOPTED,
                    Issue.Status.ASSIGNED,
                    Issue.Status.DEPLOYED,
                    Issue.Status.AWAITING_VERIFICATION,
                    Issue.Status.RESOLVED,
                ],
                'terminal_statuses': [Issue.Status.RESOLVED, Issue.Status.REJECTED, Issue.Status.DUPLICATE],
                'reopen_status': Issue.Status.REOPENED,
            },
            'solutions': {
                'statuses': dict(Pitch.Status.choices),
                'canonical_flow': [
                    Pitch.Status.SUBMITTED,
                    Pitch.Status.UNDER_REVIEW,
                    Pitch.Status.CHANGES_REQUESTED,
                    Pitch.Status.RESUBMITTED,
                    Pitch.Status.SELECTED,
                ],
                'terminal_statuses': [Pitch.Status.SELECTED, Pitch.Status.REJECTED, Pitch.Status.MERGED],
            },
            'projects': {
                'statuses': dict(Project.Status.choices),
                'canonical_flow': [
                    Project.Status.CREATED,
                    Project.Status.PLANNING,
                    Project.Status.PROTOTYPE,
                    Project.Status.PILOT,
                    Project.Status.DEPLOYMENT_READY,
                    Project.Status.DEPLOYED,
                    Project.Status.AWAITING_CITIZEN_VERIFICATION,
                    Project.Status.VERIFIED,
                ],
                'terminal_statuses': [Project.Status.VERIFIED, Project.Status.CLOSED],
                'reopen_status': Project.Status.REOPENED,
            },
            'milestones': {
                'statuses': dict(ProjectMilestone.Status.choices),
            },
            'open_calls': {
                'statuses': dict(OpenCall.Status.choices),
            },
            'adoptions': {
                'statuses': dict(Adoption.Status.choices),
            },
            'collaborator_roles': dict(ChallengeCollaborator.Role.choices),
            'discussion_topics': {
                'challenge': ['clarification', 'context', 'requirements', 'constraints', 'evidence', 'general'],
                'solution': ['technical', 'review', 'implementation', 'changes', 'mentorship', 'general'],
                'project': ['engineering', 'milestone', 'coordination', 'general'],
            }
        }, status=status.HTTP_200_OK)


from django.db.models import Q

class UniversityActionInboxView(APIView):
    """
    University Home - Action Inbox (Section 25 & P1 Issue 25).
    Surfaces all pending items requiring decisions by the university coordinator / faculty mentor:
    1. Challenges awaiting review/adoption (unadopted validated/submitted issues in university district)
    2. Student nominations awaiting decision
    3. Solutions awaiting review (pitches in SUBMITTED or RESUBMITTED status)
    4. Milestones awaiting approval (deployed/active projects)
    5. Citizen verification failures (reopened challenges requiring investigation)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if getattr(user, 'role', None) not in ['university_coordinator', 'faculty_mentor'] and not user.is_staff:
            raise PermissionDenied("Only university coordinators, mentors, or staff can access the action inbox.")

        uni = getattr(user, 'university', None)
        if not uni and not user.is_staff:
            empty_buckets = {
                'challenges_awaiting_review': {'count': 0, 'items': [], 'label': 'Challenges awaiting review/adoption'},
                'nominations_awaiting_decision': {'count': 0, 'items': [], 'label': 'Student nominations awaiting decision'},
                'student_nominations': {'count': 0, 'items': [], 'label': 'Student nominations awaiting decision'},
                'solutions_awaiting_review': {'count': 0, 'items': [], 'label': 'Solutions awaiting review'},
                'milestones_awaiting_approval': {'count': 0, 'items': [], 'label': 'Milestones awaiting approval'},
                'citizen_verification_failures': {'count': 0, 'items': [], 'label': 'Citizen verification failures'}
            }
            return Response({
                'total_pending_actions': 0,
                'buckets': empty_buckets,
                **empty_buckets
            })

        # 1. Challenges awaiting review / adoption
        ch_filter = Q(status__in=[Issue.Status.SUBMITTED, Issue.Status.VALIDATED], adoption__isnull=True)
        if uni and getattr(uni, 'district', None):
            ch_qs = Issue.objects.filter(ch_filter & (Q(district__iexact=uni.district) | Q(district='')))
            if not ch_qs.exists():
                ch_qs = Issue.objects.filter(ch_filter)
        else:
            ch_qs = Issue.objects.filter(ch_filter)

        ch_list = [
            {'id': i.id, 'title': i.title, 'district': i.district, 'category': i.category, 'status': i.status, 'created_at': i.created_at}
            for i in ch_qs.order_by('-created_at')[:10]
        ]

        # 2. Student nominations awaiting decision
        nom_filter = Q(status='pending')
        if uni:
            nom_filter &= (Q(university=uni) | Q(student__university=uni))
        nom_qs = StudentNomination.objects.filter(nom_filter).select_related('student', 'issue')
        nom_list = [
            {
                'id': n.id,
                'issue_id': n.issue_id,
                'issue_title': n.issue.title,
                'student_name': n.student.name or n.student.email,
                'rationale': n.rationale,
                'created_at': n.created_at
            }
            for n in nom_qs.order_by('-created_at')[:10]
        ]

        # 3. Solutions awaiting review
        from apps.pitches.models import Pitch, ProjectLifecycle
        pitch_filter = Q(status__in=[Pitch.Status.SUBMITTED, Pitch.Status.RESUBMITTED, Pitch.Status.UNDER_REVIEW])
        if uni:
            pitch_filter &= (Q(university=uni) | Q(issue__adoption__university=uni))
        pitch_qs = Pitch.objects.filter(pitch_filter).select_related('issue')
        sol_list = [
            {
                'id': p.id,
                'title': p.title,
                'issue_id': p.issue_id,
                'issue_title': p.issue.title,
                'version': p.version,
                'status': p.status,
                'submitted_at': p.submission_timestamp
            }
            for p in pitch_qs.order_by('-submission_timestamp')[:10]
        ]

        # 4. Milestones awaiting approval
        proj_filter = Q(outcome_status__in=['in_progress', 'deployed'])
        if uni:
            proj_filter &= (Q(pitch__university=uni) | Q(pitch__issue__adoption__university=uni))
        proj_qs = ProjectLifecycle.objects.filter(proj_filter).select_related('pitch')
        proj_list = [
            {
                'id': pr.id,
                'pitch_id': pr.pitch_id,
                'pitch_title': pr.pitch.title,
                'outcome_status': pr.outcome_status,
                'milestones': pr.milestones,
                'updated_at': pr.updated_at
            }
            for pr in proj_qs.order_by('-updated_at')[:10]
        ]

        # 5. Citizen verification failures
        fail_filter = Q(status__in=[Issue.Status.REOPENED, 'disputed'])
        if uni:
            fail_filter &= (Q(adoption__university=uni) | (Q(district__iexact=getattr(uni, 'district', ''))))
        fail_qs = Issue.objects.filter(fail_filter)
        fail_list = [
            {
                'id': f.id,
                'title': f.title,
                'district': f.district,
                'status': f.status,
                'updated_at': f.updated_at
            }
            for f in fail_qs.order_by('-updated_at')[:10]
        ]

        ch_count = ch_qs.count()
        nom_count = nom_qs.count()
        sol_count = pitch_qs.count()
        proj_count = proj_qs.count()
        fail_count = fail_qs.count()
        total_pending = ch_count + nom_count + sol_count + proj_count + fail_count

        buckets = {
            'challenges_awaiting_review': {'count': ch_count, 'items': ch_list, 'label': 'Challenges awaiting review/adoption'},
            'nominations_awaiting_decision': {'count': nom_count, 'items': nom_list, 'label': 'Student nominations awaiting decision'},
            'student_nominations': {'count': nom_count, 'items': nom_list, 'label': 'Student nominations awaiting decision'},
            'solutions_awaiting_review': {'count': sol_count, 'items': sol_list, 'label': 'Solutions awaiting review'},
            'milestones_awaiting_approval': {'count': proj_count, 'items': proj_list, 'label': 'Milestones awaiting approval'},
            'citizen_verification_failures': {'count': fail_count, 'items': fail_list, 'label': 'Citizen verification failures'},
        }

        return Response({
            'total_pending_actions': total_pending,
            'buckets': buckets,
            'challenges_awaiting_review': buckets['challenges_awaiting_review'],
            'nominations_awaiting_decision': buckets['nominations_awaiting_decision'],
            'student_nominations': buckets['student_nominations'],
            'solutions_awaiting_review': buckets['solutions_awaiting_review'],
            'milestones_awaiting_approval': buckets['milestones_awaiting_approval'],
            'citizen_verification_failures': buckets['citizen_verification_failures'],
        })
