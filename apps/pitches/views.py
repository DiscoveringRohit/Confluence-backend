from django.db import models, transaction
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound

import hashlib
import uuid
from .models import (
    Pitch, CommunityFeedback, ProjectLifecycle, PitchVersionHistory,
    SolutionEvaluation, SolutionTeamMember, ReviewSession, Project, ProjectMilestone,
    Certificate, ProjectMember
)
from .serializers import (
    PitchSerializer,
    PitchCreateSerializer,
    CommunityFeedbackSerializer,
    ProjectLifecycleSerializer,
    ReviewBoardActionSerializer,
    PitchResubmitSerializer,
    SolutionEvaluationSerializer,
    SolutionTeamMemberSerializer,
    ReviewSessionSerializer,
    ProjectSerializer,
    ProjectDetailSerializer,
    ProjectMilestoneSerializer,
    CertificateSerializer,
    ProjectMemberSerializer,
)
from apps.issues.models import Issue, DiscussionComment, ActivityEvent, log_activity
from apps.issues.serializers import DiscussionCommentSerializer, ActivityEventSerializer
from apps.users.models import User
from apps.engagements.models import IndustryEngagement
from apps.users.permissions import (
    IsStudent,
    IsUniversityCoordinator,
    IsFacultyMentor,
    IsUniversityAffiliated,
    IsCitizen,
)
from .permissions import ProjectAccessPermission

def get_pitch_by_pk_or_public_id(pk):
    if not pk:
        return None
    if str(pk).isdigit():
        return Pitch.objects.filter(models.Q(pk=int(pk)) | models.Q(public_id=str(pk))).first()
    return Pitch.objects.filter(public_id=str(pk)).first()

def get_project_by_pk_or_public_id(pk):
    if not pk:
        return None
    if str(pk).isdigit():
        return Project.objects.filter(models.Q(pk=int(pk)) | models.Q(public_id=str(pk))).first()
    return Project.objects.filter(public_id=str(pk)).first()

class PitchListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PitchCreateSerializer
        return PitchSerializer

    def get_queryset(self):
        qs = Pitch.objects.select_related('issue', 'university', 'assigned_mentor').prefetch_related('student_team', 'community_feedback').all().order_by('-created_at')
        
        issue_id = self.request.query_params.get('issue')
        mine = self.request.query_params.get('mine')
        uni_id = self.request.query_params.get('university')

        if issue_id:
            if not str(issue_id).isdigit():
                issue = Issue.objects.filter(public_id=issue_id).first()
                issue_id = issue.id if issue else None
            qs = qs.filter(issue_id=issue_id)
        if mine and self.request.user.is_authenticated:
            qs = qs.filter(student_team=self.request.user)
        if uni_id:
            qs = qs.filter(university_id=uni_id)
        elif self.request.user.is_authenticated and getattr(self.request.user, 'role', None) == 'university_coordinator':
            if self.request.user.university_id:
                qs = qs.filter(university_id=self.request.user.university_id)

        open_call_id = self.request.query_params.get('open_call')
        if open_call_id:
            qs = qs.filter(open_call_id=open_call_id)
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated or user.role != 'student':
            raise PermissionDenied("Only authenticated students can submit pitches.")

        if not user.university_id:
            raise PermissionDenied("Student must be affiliated with a university to submit a proposal.")

        issue = serializer.validated_data['issue']
        if issue.status != Issue.Status.ADOPTED:
            raise ValidationError("Pitches can only be submitted for adopted issues (open calls).")

        # Critical University Ownership Rule: Student must belong to the adopting university
        if not hasattr(issue, 'adoption') or issue.adoption.university_id != user.university_id:
            raise PermissionDenied("Students can only submit proposals for challenges adopted by their university.")

        serializer.save()


class PitchDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Pitch.objects.select_related('issue', 'university', 'assigned_mentor').prefetch_related('student_team', 'community_feedback').all()
    serializer_class = PitchSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_object(self):
        pk = self.kwargs.get('pk')
        queryset = self.filter_queryset(self.get_queryset())
        if str(pk).isdigit():
            obj = queryset.filter(models.Q(pk=int(pk)) | models.Q(public_id=str(pk))).first()
        else:
            obj = queryset.filter(public_id=str(pk)).first()
        if not obj:
            raise NotFound("Solution not found.")
        self.check_object_permissions(self.request, obj)
        return obj

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        user = request.user
        if request.method in permissions.SAFE_METHODS:
            return
        is_owner = SolutionTeamMember.objects.filter(pitch=obj, student=user, role=SolutionTeamMember.Role.OWNER).exists() or obj.student_team.filter(id=user.id).exists()
        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == obj.university_id)
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', None) in ['admin', 'gov_admin']
        if not (is_owner or is_coord or is_admin):
            raise PermissionDenied("You do not have permission to modify or delete this pitch.")

    def perform_update(self, serializer):
        user = self.request.user
        pitch = self.get_object()
        is_owner = SolutionTeamMember.objects.filter(pitch=pitch, student=user, role=SolutionTeamMember.Role.OWNER).exists() or pitch.student_team.filter(id=user.id).exists()
        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == pitch.university_id)
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', None) in ['admin', 'gov_admin']
        if not (is_owner or is_coord or is_admin):
            raise PermissionDenied("You do not have permission to edit this pitch.")

        prev_repo = pitch.repository_url
        prev_demo = pitch.demo_url
        prev_doc = pitch.documentation_url
        prev_video = pitch.video_url

        updated_pitch = serializer.save()
        version_notes = self.request.data.get('version_notes') or self.request.data.get('change_summary')
        if version_notes:
            PitchVersionHistory.objects.create(
                pitch=updated_pitch,
                version=updated_pitch.version,
                title=pitch.title,
                public_summary=pitch.public_summary,
                confidential_package=pitch.confidential_package,
                repository_url=prev_repo,
                demo_url=prev_demo,
                documentation_url=prev_doc,
                video_url=prev_video,
                submission_hash=pitch.submission_hash,
                change_summary=version_notes,
                actor=user
            )
            updated_pitch.version += 1
            updated_pitch.submission_timestamp = timezone.now()
            updated_pitch.submission_hash = updated_pitch.compute_hash()
            updated_pitch.save(update_fields=['version', 'submission_timestamp', 'submission_hash'])


class CommunityFeedbackCreateView(generics.CreateAPIView):
    """
    Submit community feedback on a pitch's public_summary.
    Restricted to: citizen, university_coordinator, faculty_mentor, gov_admin.
    Students and industry partners cannot post community feedback — students
    have a conflict of interest (competing pitches); industry partners use the
    engagement channel instead.
    """
    serializer_class = CommunityFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    # Roles explicitly NOT allowed to submit feedback
    _BLOCKED_ROLES = {'student', 'industry_partner'}

    def perform_create(self, serializer):
        user = self.request.user
        if user.role in self._BLOCKED_ROLES:
            raise PermissionDenied(
                f"Users with role '{user.role}' cannot submit community feedback. "
                "Students use the pitch submission channel; industry partners use the engagement channel."
            )

        pitch_id = self.kwargs['pitch_id']
        pitch = get_pitch_by_pk_or_public_id(pitch_id)
        if not pitch:
            raise ValidationError("Pitch does not exist.")

        serializer.save(pitch=pitch, citizen=user)


class ScoreFeedbackView(APIView):
    """
    Mentor or university coordinator scores the relevance of a citizen's feedback (1-10).
    """
    permission_classes = [permissions.IsAuthenticated, IsUniversityAffiliated]

    def post(self, request, pk):
        try:
            feedback = CommunityFeedback.objects.get(pk=pk)
        except CommunityFeedback.DoesNotExist:
            return Response({'error': 'Feedback record not found'}, status=status.HTTP_404_NOT_FOUND)

        score = request.data.get('relevance_score')
        notes = request.data.get('mentor_notes', '')
        share = request.data.get('is_shared_with_students', True)

        if score is None or not (1 <= int(score) <= 10):
            return Response({'error': 'Relevance score must be an integer between 1 and 10'}, status=status.HTTP_400_BAD_REQUEST)

        feedback.relevance_score = int(score)
        feedback.mentor_notes = notes
        feedback.is_shared_with_students = bool(share)
        feedback.save(update_fields=['relevance_score', 'mentor_notes', 'is_shared_with_students'])

        return Response(CommunityFeedbackSerializer(feedback, context={'request': request}).data)


class SolutionEvaluationListCreateView(generics.ListCreateAPIView):
    """
    List or create evaluations for a pitch (P0 Issue 12).
    - Only university coordinators or assigned faculty mentors of the pitch's university can evaluate.
    - Persists technical feasibility, social impact, cost, scalability, sustainability, innovation, and readiness.
    """
    serializer_class = SolutionEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        pitch_id = self.kwargs.get('pitch_id')
        user = self.request.user

        # Access check: Own student team, university coordinators/mentors, or staff
        pitch = get_pitch_by_pk_or_public_id(pitch_id)
        if not pitch:
            return SolutionEvaluation.objects.none()

        is_own_team = pitch.student_team.filter(id=user.id).exists()
        is_uni = getattr(user, 'role', None) in ['university_coordinator', 'faculty_mentor'] and user.university_id == pitch.university_id
        if not (is_own_team or is_uni or user.is_staff):
            raise PermissionDenied("You do not have permission to view evaluations for this solution.")

        return SolutionEvaluation.objects.filter(pitch_id=pitch.id).select_related('reviewer').order_by('-created_at')

    def create(self, request, *args, **kwargs):
        pitch_id = self.kwargs.get('pitch_id')
        pitch = get_pitch_by_pk_or_public_id(pitch_id)
        if not pitch:
            raise NotFound({'pitch': 'Pitch does not exist.'})

        user = request.user
        # Must belong to the same university as the pitch and be coordinator or assigned mentor (Issue 28)
        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == pitch.university_id)
        is_assigned_mentor = (getattr(user, 'role', None) == 'faculty_mentor' and user.university_id == pitch.university_id and pitch.assigned_mentor_id == user.id)
        if not (is_coord or is_assigned_mentor or user.is_staff):
            raise PermissionDenied("Only maintaining university coordinators or assigned faculty mentors can submit evaluations.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        evaluation, created = SolutionEvaluation.objects.update_or_create(
            pitch=pitch,
            reviewer=user,
            defaults=serializer.validated_data
        )

        if pitch.status in [Pitch.Status.SUBMITTED, Pitch.Status.RESUBMITTED]:
            pitch.status = Pitch.Status.UNDER_REVIEW
            pitch.save(update_fields=['status'])

        try:
            log_activity(
                issue=pitch.issue,
                actor=user,
                event_type='SOLUTION_EVALUATION',
                description=f"Reviewer {user.name or user.email} scored Solution #{pitch.id}: {evaluation.total_score}/100 ({evaluation.get_recommendation_display()})",
                object_type='pitch',
                object_id=str(pitch.id),
                metadata={'total_score': evaluation.total_score, 'recommendation': evaluation.recommendation}
            )
        except Exception:
            pass

        out_serializer = self.get_serializer(evaluation)
        headers = self.get_success_headers(out_serializer.data)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class SolutionEvaluationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete an evaluation (reviewer only).
    """
    queryset = SolutionEvaluation.objects.all()
    serializer_class = SolutionEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_update(self, serializer):
        if self.get_object().reviewer != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You can only edit your own evaluation.")
        serializer.save()


class ReviewBoardActionView(APIView):
    """
    University Review Board Actions (Section 27, 28, 29 & P1 Issues 27-29):
    - Start review / transition to UNDER_REVIEW
    - Request revisions / changes with mandatory feedback
    - Assign faculty mentor (enforcing role and same maintaining university)
    - Select winning pitch outright
    - Merge two complementary pitches into one joint team
    - Reject pitch
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        pitch = get_pitch_by_pk_or_public_id(pk)
        if not pitch:
            return Response({'error': 'Pitch not found.'}, status=status.HTTP_404_NOT_FOUND)

        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == pitch.university_id)
        is_assigned_mentor = (getattr(user, 'role', None) == 'faculty_mentor' and user.university_id == pitch.university_id and pitch.assigned_mentor_id == user.id)

        if not (is_coord or is_assigned_mentor or user.is_staff):
            raise PermissionDenied("Only maintaining university coordinators or assigned faculty mentors can perform review actions on this solution.")

        serializer = ReviewBoardActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        action = data['action']

        if action == 'reject':
            if not (is_coord or user.is_staff):
                raise PermissionDenied("Only university coordinators can reject pitches.")
            if pitch.status in (Pitch.Status.SELECTED, Pitch.Status.MERGED):
                return Response(
                    {'error': f'Cannot reject a pitch that is already {pitch.status}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            feedback_text = data.get(
                'review_feedback',
                'Your proposal was reviewed by the university board and has been withdrawn from this open call. '
                'The feedback and work remain archived in the university vault for future reference.'
            )
            pitch.status = Pitch.Status.REJECTED
            pitch.review_feedback = feedback_text
            pitch.save(update_fields=['status', 'review_feedback'])
            return Response({
                'message': f'Pitch #{pitch.id} rejected. The open call for the issue remains active.',
                'pitch_id': pitch.id,
                'status': pitch.status,
                'review_feedback': pitch.review_feedback,
            })

        elif action == 'assign_mentor':
            if not (is_coord or user.is_staff):
                raise PermissionDenied("Only university coordinators can assign faculty mentors.")
            mentor_id = data.get('mentor_id')
            if not mentor_id:
                return Response({'error': 'mentor_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                mentor = User.objects.get(pk=mentor_id)
            except User.DoesNotExist:
                return Response({'error': 'Valid faculty mentor required.'}, status=status.HTTP_400_BAD_REQUEST)

            if mentor.role != 'faculty_mentor':
                return Response({'error': 'Assigned mentor must have the faculty_mentor role.'}, status=status.HTTP_400_BAD_REQUEST)

            # Issue 29: Mentor-university validation against challenge maintaining university
            maintainer_uni_id = pitch.issue.adoption.university_id if hasattr(pitch.issue, 'adoption') else pitch.university_id
            if mentor.university_id != maintainer_uni_id:
                return Response({
                    'error': f'Assigned mentor must belong to the maintaining university ({pitch.university.name}).'
                }, status=status.HTTP_400_BAD_REQUEST)

            pitch.assigned_mentor = mentor
            pitch.save(update_fields=['assigned_mentor'])
            return Response({'message': f'Mentor {mentor.name} assigned to pitch.', 'mentor_id': mentor.id})

        elif action == 'select_winner':
            if not (is_coord or user.is_staff):
                raise PermissionDenied("Only university coordinators can select the winning pitch.")

            mentor_id = data.get('mentor_id') or request.data.get('mentor_id')
            if mentor_id:
                mentor = User.objects.filter(id=mentor_id, role='faculty_mentor').first()
                if mentor:
                    pitch.assigned_mentor = mentor

            pitch.status = Pitch.Status.SELECTED
            pitch.review_feedback = data.get('review_feedback', 'Selected as winning solution by University Review Board.')
            update_fields = ['status', 'review_feedback']
            if pitch.assigned_mentor_id:
                update_fields.append('assigned_mentor')
            pitch.save(update_fields=update_fields)

            # Transition issue to 'assigned'
            issue = pitch.issue
            issue.transition_status(
                Issue.Status.ASSIGNED,
                actor=request.user,
                reason=f"Winning pitch '{pitch.title}' selected by university review board."
            )

            # Create or get Project (Issue 32 & 33)
            project, p_created = Project.objects.get_or_create(
                solution=pitch,
                defaults={
                    'challenge': pitch.issue,
                    'university': pitch.university,
                    'mentor': pitch.assigned_mentor,
                    'title': pitch.title,
                    'status': Project.Status.PLANNING,
                    'start_date': timezone.now().date(),
                }
            )
            if not p_created and pitch.assigned_mentor and not project.mentor:
                project.mentor = pitch.assigned_mentor
                project.save(update_fields=['mentor'])
            project.team.set(pitch.student_team.all())
            for collab in pitch.collaborators.filter(status=SolutionTeamMember.Status.ACTIVE):
                role_title = 'Lead' if collab.role == SolutionTeamMember.Role.OWNER else collab.get_role_display()
                ProjectMember.objects.get_or_create(
                    project=project,
                    user=collab.student,
                    defaults={'role': role_title}
                )
            for st in pitch.student_team.all():
                ProjectMember.objects.get_or_create(
                    project=project,
                    user=st,
                    defaults={'role': 'Developer'}
                )
            if p_created and not project.milestones.exists():
                default_ms = [
                    ('System Architecture & Design Freeze', '30 days', 'System block diagrams, API schemas, and hardware architecture specification frozen.'),
                    ('Working Prototype & Lab Validation', '60 days', 'Bench testing, hardware fabrication, and unit test pass reports.'),
                    ('Field Pilot Deployment in District', '90 days', 'Live pilot test with local community beneficiaries in the targeted district.'),
                    ('Final Handover & Citizen Sign-off Prep', '120 days', 'User manual, telemetry logs, and citizen verification readiness package.')
                ]
                for order_idx, (m_title, m_due, m_desc) in enumerate(default_ms, start=1):
                    ProjectMilestone.objects.create(
                        project=project,
                        order=order_idx,
                        title=m_title,
                        due_date=m_due,
                        description=m_desc,
                        status=ProjectMilestone.Status.PENDING
                    )

            # Create or get ProjectLifecycle (legacy compatibility)
            lifecycle, _ = ProjectLifecycle.objects.get_or_create(
                pitch=pitch,
                defaults={
                    'milestones': [
                        {'id': 1, 'title': 'System Architecture & Design Freeze', 'due_date': '30 days', 'completed': False},
                        {'id': 2, 'title': 'Working Prototype & Lab Validation', 'due_date': '60 days', 'completed': False},
                        {'id': 3, 'title': 'Field Pilot Deployment in District', 'due_date': '90 days', 'completed': False},
                        {'id': 4, 'title': 'Citizen Sign-off & Impact Assessment', 'due_date': '120 days', 'completed': False}
                    ]
                }
            )

            # Mark other competing pitches for this issue as rejected with constructive feedback
            competing = Pitch.objects.filter(issue=issue).exclude(id=pitch.id).exclude(status=Pitch.Status.MERGED)
            for other_pitch in competing:
                other_pitch.status = Pitch.Status.REJECTED
                if not other_pitch.review_feedback:
                    other_pitch.review_feedback = "Your proposal was reviewed thoroughly. Another pitch was selected for deployment, but your proposal remains archived in the university vault for future calls."
                other_pitch.save(update_fields=['status', 'review_feedback'])

            # Automatically link any active/requested industry engagements for this problem to the selected pitch
            IndustryEngagement.objects.filter(issue=issue, pitch__isnull=True).update(pitch=pitch)

            return Response({
                'message': 'Winning pitch selected! Issue transitioned to Assigned.',
                'pitch': PitchSerializer(pitch, context={'request': request}).data,
                'project': ProjectSerializer(project).data,
                'lifecycle': ProjectLifecycleSerializer(lifecycle).data
            })

        elif action == 'merge_pitches':
            merge_with_id = data.get('merge_with_pitch_id')
            if not merge_with_id:
                return Response({'error': 'merge_with_pitch_id is required to merge.'}, status=status.HTTP_400_BAD_REQUEST)

            second_pitch = get_pitch_by_pk_or_public_id(merge_with_id)
            if not second_pitch or second_pitch.issue_id != pitch.issue_id or second_pitch.university_id != request.user.university_id:
                return Response({'error': 'Second pitch not found on this issue.'}, status=status.HTTP_404_NOT_FOUND)

            # Merge second_pitch team into pitch
            for member in second_pitch.student_team.all():
                pitch.student_team.add(member)

            pitch.status = Pitch.Status.SELECTED
            pitch.title = f"[Joint Team] {pitch.title} + {second_pitch.title}"
            pitch.review_feedback = f"Merged with Pitch #{second_pitch.id} due to complementary technical strengths."
            pitch.save()

            second_pitch.status = Pitch.Status.MERGED
            second_pitch.merged_into = pitch
            second_pitch.review_feedback = f"Merged into Pitch #{pitch.id} into a single collaborative team."
            second_pitch.save()

            issue = pitch.issue
            issue.transition_status(
                Issue.Status.ASSIGNED,
                actor=request.user,
                reason=f"Pitches #{pitch.id} and #{second_pitch.id} merged into joint team."
            )

            # Automatically link any active/requested industry engagements for this problem to the primary pitch
            IndustryEngagement.objects.filter(issue=issue, pitch__isnull=True).update(pitch=pitch)

            # (consistent with select_winner behavior)
            remaining = Pitch.objects.filter(issue=issue).exclude(
                id__in=[pitch.id, second_pitch.id]
            ).exclude(status__in=[Pitch.Status.MERGED, Pitch.Status.REJECTED])
            for other_pitch in remaining:
                other_pitch.status = Pitch.Status.REJECTED
                if not other_pitch.review_feedback:
                    other_pitch.review_feedback = (
                        "Your proposal was reviewed thoroughly. Two complementary pitches were merged "
                        "into a joint team for deployment. Your proposal remains archived in the university "
                        "vault for future calls."
                    )
                other_pitch.save(update_fields=['status', 'review_feedback'])

            lifecycle, _ = ProjectLifecycle.objects.get_or_create(
                pitch=pitch,
                defaults={
                    'milestones': [
                        {'id': 1, 'title': 'Combined Team Architecture Integration', 'due_date': '30 days', 'completed': False},
                        {'id': 2, 'title': 'Integrated Prototype Assembly', 'due_date': '60 days', 'completed': False},
                        {'id': 3, 'title': 'District Pilot Deployment', 'due_date': '90 days', 'completed': False},
                    ]
                }
            )

            # Auto-provision Project container for merged solution
            project, p_created = Project.objects.get_or_create(
                solution=pitch,
                challenge=pitch.issue,
                university=request.user.university,
                defaults={
                    'title': pitch.title,
                    'status': Project.Status.PLANNING,
                    'mentor': pitch.assigned_mentor
                }
            )
            if p_created:
                for member in pitch.student_team.all():
                    project.team.add(member)

            return Response({
                'message': f'Pitches #{pitch.id} and #{second_pitch.id} successfully merged into a single collaborative team!',
                'pitch': PitchSerializer(pitch, context={'request': request}).data,
                'project': ProjectSerializer(project).data,
                'lifecycle': ProjectLifecycleSerializer(lifecycle).data
            })

        elif action == 'request_changes':
            feedback = data.get('review_feedback', '').strip()
            if not feedback:
                return Response({'error': 'review_feedback is required when requesting revisions.'}, status=status.HTTP_400_BAD_REQUEST)

            pitch.status = Pitch.Status.CHANGES_REQUESTED
            pitch.review_feedback = feedback
            pitch.save(update_fields=['status', 'review_feedback'])

            try:
                log_activity(
                    issue=pitch.issue,
                    actor=request.user,
                    event_type='CHANGES_REQUESTED',
                    description=f"University review board requested revisions on Solution #{pitch.id}: {feedback[:60]}",
                    object_type='pitch',
                    object_id=str(pitch.id)
                )
            except Exception:
                pass

            return Response({
                'message': f'Changes requested for Solution #{pitch.id}. Student team notified.',
                'pitch': PitchSerializer(pitch, context={'request': request}).data
            })

        elif action == 'start_review':
            pitch.status = Pitch.Status.UNDER_REVIEW
            pitch.save(update_fields=['status'])
            try:
                log_activity(
                    issue=pitch.issue,
                    actor=request.user,
                    event_type='SOLUTION_UNDER_REVIEW',
                    description=f"University review board began reviewing Solution #{pitch.id}",
                    object_type='pitch',
                    object_id=str(pitch.id)
                )
            except Exception:
                pass
            return Response({
                'message': f'Solution #{pitch.id} is now under review.',
                'pitch': PitchSerializer(pitch, context={'request': request}).data
            })

        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


class ResubmitPitchView(APIView):
    """
    Student team submits an updated revision after changes are requested (P0 Issue 7 & 9).
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request, pk):
        pitch = get_pitch_by_pk_or_public_id(pk)
        if not pitch:
            return Response({'error': 'Pitch not found'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if not pitch.student_team.filter(id=user.id).exists():
            raise PermissionDenied("Only members of the submitting student team can resubmit revisions.")

        if pitch.status != Pitch.Status.CHANGES_REQUESTED:
            return Response({'error': f'Cannot resubmit pitch in {pitch.status} state. Changes must be requested first.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PitchResubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if 'title' in data and data['title']:
            pitch.title = data['title']
        if 'public_summary' in data and data['public_summary']:
            pitch.public_summary = data['public_summary']
        if 'repository_url' in data:
            pitch.repository_url = data['repository_url']
        if 'demo_url' in data:
            pitch.demo_url = data['demo_url']
        if 'documentation_url' in data:
            pitch.documentation_url = data['documentation_url']
        if 'video_url' in data:
            pitch.video_url = data['video_url']
        pitch.confidential_package = data['confidential_package']
        pitch.version += 1
        pitch.submission_timestamp = timezone.now()
        pitch.submission_hash = pitch.compute_hash()
        pitch.status = Pitch.Status.RESUBMITTED
        pitch.save()

        # Record version snapshot in history (P0 Issue 9 & P1 Issue 17)
        PitchVersionHistory.objects.create(
            pitch=pitch,
            version=pitch.version,
            title=pitch.title,
            public_summary=pitch.public_summary,
            confidential_package=pitch.confidential_package,
            repository_url=pitch.repository_url,
            demo_url=pitch.demo_url,
            documentation_url=pitch.documentation_url,
            video_url=pitch.video_url,
            submission_hash=pitch.submission_hash,
            change_summary=data['change_summary'],
            actor=user
        )

        try:
            log_activity(
                issue=pitch.issue,
                actor=user,
                event_type='SOLUTION_RESUBMITTED',
                description=f"Student {user.name or user.email} resubmitted Solution #{pitch.id} (v{pitch.version}): {data['change_summary'][:60]}",
                object_type='pitch',
                object_id=str(pitch.id)
            )
        except Exception:
            pass

        return Response({
            'message': f'Solution #{pitch.id} revised and resubmitted successfully (v{pitch.version})!',
            'pitch': PitchSerializer(pitch, context={'request': request}).data
        })


class UpdateMilestonesView(APIView):
    """
    Update project milestones, deliverables, and outcome status.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            lifecycle = ProjectLifecycle.objects.get(pk=pk)
        except ProjectLifecycle.DoesNotExist:
            return Response({'error': 'Project lifecycle not found'}, status=status.HTTP_404_NOT_FOUND)

        # Only assigned team, university coordinator, or mentor can update
        user = request.user
        pitch = lifecycle.pitch
        is_team_member = pitch.student_team.filter(id=user.id).exists()
        is_coord = (user.role == 'university_coordinator' and user.university_id == pitch.university_id)
        is_mentor = (user.id == pitch.assigned_mentor_id)

        if not (is_team_member or is_coord or is_mentor or user.is_staff):
            raise PermissionDenied("You do not have permission to update this project's milestones.")

        milestones = request.data.get('milestones')
        deliverables = request.data.get('deliverables')
        test_results = request.data.get('test_results')
        ip_records = request.data.get('ip_records')
        outcome_status = request.data.get('outcome_status')

        if milestones is not None:
            lifecycle.milestones = milestones
        if deliverables is not None:
            lifecycle.deliverables = deliverables
        if test_results is not None:
            lifecycle.test_results = test_results
        if ip_records is not None:
            lifecycle.ip_records = ip_records
        if outcome_status in ['in_progress', 'deployed', 'abandoned']:
            lifecycle.outcome_status = outcome_status
            if outcome_status == 'deployed':
                lifecycle.deployed_at = timezone.now()
                # Mandatory citizen verification gate (P0 Issue 10):
                # Transition issue to AWAITING_VERIFICATION (not direct RESOLVED)
                pitch.issue.transition_status(
                    Issue.Status.AWAITING_VERIFICATION,
                    actor=request.user,
                    reason="Project marked as deployed in field. Citizen verification requested."
                )
                try:
                    log_activity(
                        issue=pitch.issue,
                        actor=request.user,
                        event_type='PROJECT_DEPLOYED',
                        description="Project deployed in field. Awaiting citizen verification.",
                        object_type='project',
                        object_id=str(lifecycle.id)
                    )
                except Exception:
                    pass

        lifecycle.save()
        return Response(ProjectLifecycleSerializer(lifecycle).data)


class SolutionTeamMemberView(APIView):
    """
    Manage solution collaborators and roles (Section 22 & P1 Issue 20).
    Only team members, maintaining coordinators, or staff can modify roles.
    Enforces student role and university matching.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pitch_id):
        pitch = get_pitch_by_pk_or_public_id(pitch_id)
        if not pitch:
            return Response({'error': 'Solution not found.'}, status=status.HTTP_404_NOT_FOUND)
        members = SolutionTeamMember.objects.filter(pitch=pitch).select_related('student')
        return Response(SolutionTeamMemberSerializer(members, many=True).data)

    def post(self, request, pitch_id):
        pitch = get_pitch_by_pk_or_public_id(pitch_id)
        if not pitch:
            return Response({'error': 'Solution not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_owner_or_member = pitch.student_team.filter(id=user.id).exists()
        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == pitch.university_id)
        if not (is_owner_or_member or is_coord or user.is_staff):
            raise PermissionDenied("You do not have permission to manage team members for this solution.")

        student_id = request.data.get('student_id') or request.data.get('user_id')
        role = request.data.get('role', SolutionTeamMember.Role.DEVELOPER).lower()
        member_status = request.data.get('status', SolutionTeamMember.Status.ACTIVE).lower()

        if not student_id:
            return Response({'error': 'student_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            student = User.objects.get(pk=student_id)
        except User.DoesNotExist:
            return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

        if student.role != 'student':
            return Response({'error': 'Only students can be added to the team.'}, status=status.HTTP_400_BAD_REQUEST)

        if student.university_id != pitch.university_id:
            return Response({'error': f'Team member must be enrolled at the same university ({pitch.university.name}).'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if already an active member when adding
        existing = SolutionTeamMember.objects.filter(pitch=pitch, student=student).first()
        if existing and existing.status == SolutionTeamMember.Status.ACTIVE and request.method == 'POST' and not request.data.get('update_role'):
            return Response({'error': 'User is already a member of this solution team.'}, status=status.HTTP_400_BAD_REQUEST)

        member, _ = SolutionTeamMember.objects.update_or_create(
            pitch=pitch,
            student=student,
            defaults={'role': role, 'status': member_status}
        )
        pitch.student_team.add(student)

        return Response(SolutionTeamMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    def delete(self, request, pitch_id, member_id=None):
        pitch = get_pitch_by_pk_or_public_id(pitch_id)
        if not pitch:
            return Response({'error': 'Solution not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_owner = SolutionTeamMember.objects.filter(pitch=pitch, student=user, role=SolutionTeamMember.Role.OWNER).exists()
        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == pitch.university_id)
        if not (is_owner or is_coord or user.is_staff):
            raise PermissionDenied("Only solution owners or university coordinators can remove team members.")

        target_id = member_id or request.data.get('member_id') or request.data.get('student_id') or request.data.get('user_id')
        if not target_id:
            return Response({'error': 'member_id or student_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        member = SolutionTeamMember.objects.filter(pitch=pitch).filter(
            models.Q(id=target_id) | models.Q(student_id=target_id)
        ).first()
        if not member:
            return Response({'error': 'Member not found on this team.'}, status=status.HTTP_404_NOT_FOUND)

        # Cannot remove sole active owner
        if member.role == SolutionTeamMember.Role.OWNER:
            owner_count = SolutionTeamMember.objects.filter(
                pitch=pitch,
                role=SolutionTeamMember.Role.OWNER,
                status=SolutionTeamMember.Status.ACTIVE
            ).count()
            if owner_count <= 1:
                return Response({'error': 'Cannot remove the sole owner of the solution.'}, status=status.HTTP_400_BAD_REQUEST)

        member.status = SolutionTeamMember.Status.REMOVED
        member.save(update_fields=['status'])
        pitch.student_team.remove(member.student)

        return Response({'message': 'Team member removed from solution.'})


class ProjectMemberView(APIView):
    """
    Manage project members, roles and assignments.
    Only project members, maintaining coordinators, faculty mentors, or staff can modify members.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, project_id):
        project = get_project_by_pk_or_public_id(project_id)
        if not project:
            return Response({'error': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)
        members = ProjectMember.objects.filter(project=project, left_at__isnull=True).select_related('user')
        return Response(ProjectMemberSerializer(members, many=True).data)

    def post(self, request, project_id):
        project = get_project_by_pk_or_public_id(project_id)
        if not project:
            return Response({'error': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_member = project.team.filter(id=user.id).exists()
        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == project.university_id)
        is_mentor = (project.mentor_id == user.id)
        if not (is_member or is_coord or is_mentor or user.is_staff):
            raise PermissionDenied("You do not have permission to manage members for this project.")

        target_user_id = request.data.get('user_id') or request.data.get('student_id')
        role = request.data.get('role', 'Developer')

        if not target_user_id:
            return Response({'error': 'user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_user = User.objects.get(pk=target_user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        member, _ = ProjectMember.objects.update_or_create(
            project=project,
            user=target_user,
            defaults={'role': role, 'left_at': None}
        )
        project.team.add(target_user)

        return Response(ProjectMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    def delete(self, request, project_id, member_id=None):
        project = get_project_by_pk_or_public_id(project_id)
        if not project:
            return Response({'error': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == project.university_id)
        is_mentor = (project.mentor_id == user.id)
        if not (is_coord or is_mentor or user.is_staff):
            raise PermissionDenied("Only university coordinators, faculty mentors, or admins can remove project members.")

        target_id = member_id or request.data.get('member_id') or request.data.get('user_id')
        if not target_id:
            return Response({'error': 'member_id or user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        member = ProjectMember.objects.filter(project=project).filter(
            models.Q(id=target_id) | models.Q(user_id=target_id)
        ).first()
        if not member:
            return Response({'error': 'Member not found on this project.'}, status=status.HTTP_404_NOT_FOUND)

        member.left_at = timezone.now()
        member.save(update_fields=['left_at'])
        project.team.remove(member.user)

        return Response({'message': 'Member removed from project.'})



class PitchDiscussionListCreateView(generics.ListCreateAPIView):
    """
    Solution technical discussion system (Section 40 & P1 Issue 18).
    Students, faculty mentors, and coordinators can collaborate on implementation details.
    """
    serializer_class = DiscussionCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        pitch_id = self.kwargs.get('pitch_id')
        pitch = get_pitch_by_pk_or_public_id(pitch_id)
        resolved_id = pitch.id if pitch else None
        qs = DiscussionComment.objects.filter(
            pitch_id=resolved_id,
            target_type='solution'
        ).select_related('author').order_by('created_at')
        cat = self.request.query_params.get('category')
        if cat:
            qs = qs.filter(category=cat.lower())
        return qs

    def perform_create(self, serializer):
        pitch_id = self.kwargs.get('pitch_id')
        pitch = get_pitch_by_pk_or_public_id(pitch_id)
        if not pitch:
            raise ValidationError({'pitch': 'Solution does not exist.'})

        cat = self.request.data.get('category', 'general')
        comment = serializer.save(
            author=self.request.user,
            pitch=pitch,
            target_type='solution',
            category=cat
        )

        try:
            log_activity(
                issue=pitch.issue,
                actor=self.request.user,
                event_type='SOLUTION_DISCUSSION',
                description=f"{self.request.user.name or self.request.user.email} commented on Solution #{pitch.id}: {comment.content[:50]}",
                object_type='discussion',
                object_id=str(comment.id)
            )
        except Exception:
            pass


# -------------------------------------------------------------------------
# Issue 31: Review Session Views
# -------------------------------------------------------------------------
class ReviewSessionListCreateView(generics.ListCreateAPIView):
    """
    List and create scheduled evaluation board sessions (Issue 31).
    """
    serializer_class = ReviewSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = ReviewSession.objects.all().select_related('university', 'challenge', 'pitch', 'created_by')

        # Filter by university if university-affiliated
        if getattr(user, 'role', None) in ['university_coordinator', 'faculty_mentor'] and user.university_id:
            qs = qs.filter(university_id=user.university_id)
        elif getattr(user, 'role', None) == 'student':
            qs = qs.filter(pitch__student_team=user)
        elif not user.is_staff:
            if user.university_id:
                qs = qs.filter(university_id=user.university_id)

        # Query filters
        challenge_id = self.request.query_params.get('challenge') or self.request.query_params.get('issue_id')
        if challenge_id:
            qs = qs.filter(challenge_id=challenge_id)
        pitch_id = self.request.query_params.get('pitch') or self.request.query_params.get('pitch_id')
        if pitch_id:
            qs = qs.filter(pitch_id=pitch_id)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.order_by('-scheduled_at')

    def create(self, request, *args, **kwargs):
        user = request.user
        if not (getattr(user, 'role', None) in ['university_coordinator', 'faculty_mentor'] or user.is_staff):
            raise PermissionDenied("Only university coordinators or faculty mentors can schedule evaluation sessions.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        if not (getattr(user, 'role', None) in ['university_coordinator', 'faculty_mentor'] or user.is_staff):
            raise PermissionDenied("Only university coordinators or faculty mentors can schedule evaluation sessions.")

        university = user.university
        pitch = serializer.validated_data.get('pitch')
        challenge = serializer.validated_data.get('challenge')
        if pitch and not university:
            university = pitch.university
        if challenge and not university and hasattr(challenge, 'adoption'):
            university = challenge.adoption.university
        if not university:
            raise ValidationError({'university': 'A valid university affiliation is required to schedule a review session.'})

        session = serializer.save(
            created_by=user,
            university=university
        )

        target_issue = challenge or (pitch.issue if pitch else None)
        if target_issue:
            try:
                log_activity(
                    issue=target_issue,
                    actor=user,
                    event_type='REVIEW_SESSION_SCHEDULED',
                    description=f"Evaluation board scheduled for {session.scheduled_at.strftime('%b %d, %Y at %H:%M')}: {session.title}",
                    object_type='review_session',
                    object_id=str(session.id)
                )
            except Exception:
                pass


class ReviewSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or cancel a scheduled review session (Issue 31).
    """
    serializer_class = ReviewSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ReviewSession.objects.all()

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if not (user.is_staff or (getattr(user, 'role', None) in ['university_coordinator', 'faculty_mentor'] and user.university_id == instance.university_id)):
            raise PermissionDenied("Only authorized university review board members can update this session.")
        serializer.save()


# -------------------------------------------------------------------------
# Issue 32 & 33: Project Views & States
# -------------------------------------------------------------------------
class ProjectListCreateView(generics.ListCreateAPIView):
    """
    List and create real Project containers for selected solutions (Issue 32 & 33).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return ProjectSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Project.objects.all().select_related('solution', 'challenge', 'university', 'mentor').prefetch_related('team', 'milestones')

        if getattr(user, 'role', None) in ['university_coordinator', 'faculty_mentor'] and user.university_id:
            qs = qs.filter(university_id=user.university_id)
        elif getattr(user, 'role', None) == 'student':
            qs = qs.filter(team=user)
        elif getattr(user, 'role', None) == 'citizen':
            qs = qs.filter(challenge__submitted_by=user)
        elif not user.is_staff:
            if user.university_id:
                qs = qs.filter(university_id=user.university_id)

        challenge_id = self.request.query_params.get('challenge') or self.request.query_params.get('issue_id')
        if challenge_id:
            qs = qs.filter(challenge_id=challenge_id)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        user = self.request.user
        if not (getattr(user, 'role', None) == 'university_coordinator' or user.is_staff):
            raise PermissionDenied("Only university coordinators can create projects.")
        project = serializer.save()
        # Initialize default milestones if empty
        if not project.milestones.exists():
            default_ms = [
                ('System Architecture & Design Freeze', '30 days', 'System block diagrams, API schemas, and hardware architecture specification frozen.'),
                ('Working Prototype & Lab Validation', '60 days', 'Bench testing, hardware fabrication, and unit test pass reports.'),
                ('Field Pilot Deployment in District', '90 days', 'Live pilot test with local community beneficiaries in the targeted district.'),
                ('Final Handover & Citizen Sign-off Prep', '120 days', 'User manual, telemetry logs, and citizen verification readiness package.')
            ]
            for order_idx, (m_title, m_due, m_desc) in enumerate(default_ms, start=1):
                ProjectMilestone.objects.create(
                    project=project,
                    order=order_idx,
                    title=m_title,
                    due_date=m_due,
                    description=m_desc,
                    status=ProjectMilestone.Status.PENDING
                )


class ProjectDetailView(generics.RetrieveUpdateAPIView):
    """
    Detailed project views with nested milestone roadmaps (Issue 32 & 33).
    Secured with object-level permissions and role-filtered queryset (C-02).
    """
    permission_classes = [permissions.IsAuthenticated, ProjectAccessPermission]
    serializer_class = ProjectDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Project.objects.all().select_related(
            'solution', 'challenge', 'university', 'mentor'
        ).prefetch_related('team', 'milestones', 'industry_engagements')

        if not user or not user.is_authenticated:
            return qs.none()

        if user.is_staff or getattr(user, 'role', None) == 'gov_admin':
            return qs

        if getattr(user, 'role', None) in ['university_coordinator', 'faculty_mentor'] and user.university_id:
            return qs.filter(models.Q(university_id=user.university_id) | models.Q(mentor_id=user.id))

        if getattr(user, 'role', None) == 'student':
            return qs.filter(team=user)

        if getattr(user, 'role', None) == 'citizen':
            return qs.filter(challenge__submitted_by=user)

        if getattr(user, 'role', None) == 'industry_partner' and user.organization_id:
            return qs.filter(industry_engagements__industry_org_id=user.organization_id)

        if user.university_id:
            return qs.filter(university_id=user.university_id)

        return qs.none()

    def get_object(self):
        pk = self.kwargs.get('pk')
        queryset = self.filter_queryset(self.get_queryset())
        if str(pk).isdigit():
            obj = queryset.filter(models.Q(pk=int(pk)) | models.Q(public_id=str(pk))).first()
        else:
            obj = queryset.filter(public_id=str(pk)).first()
        if not obj:
            raise NotFound("Project not found.")
        self.check_object_permissions(self.request, obj)
        return obj


# -------------------------------------------------------------------------
# Issue 34: Project Milestone Management & Review
# -------------------------------------------------------------------------
class ProjectMilestoneListCreateView(generics.ListCreateAPIView):
    """
    List and create milestones for a project (Issue 34).
    """
    serializer_class = ProjectMilestoneSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        project = get_project_by_pk_or_public_id(project_id)
        resolved_id = project.id if project else None
        return ProjectMilestone.objects.filter(project_id=resolved_id).select_related('owner', 'reviewer').order_by('order', 'created_at')

    def perform_create(self, serializer):
        user = self.request.user
        project_id = self.kwargs.get('project_id')
        project = get_project_by_pk_or_public_id(project_id)
        if not project:
            raise NotFound({'project': 'Project does not exist.'})

        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == project.university_id)
        is_mentor = (user.id == project.mentor_id)
        is_team = project.team.filter(id=user.id).exists()
        if not (is_coord or is_mentor or is_team or user.is_staff):
            raise PermissionDenied("You do not have permission to add milestones to this project.")

        serializer.save(project=project)


class ProjectMilestoneDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or submit evidence for a specific milestone (Issue 34).
    """
    serializer_class = ProjectMilestoneSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        if project_id:
            project = get_project_by_pk_or_public_id(project_id)
            resolved_id = project.id if project else None
            return ProjectMilestone.objects.filter(project_id=resolved_id)
        return ProjectMilestone.objects.all()

    def perform_update(self, serializer):
        user = self.request.user
        milestone = self.get_object()
        project = milestone.project

        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == project.university_id)
        is_mentor = (user.id == project.mentor_id)
        is_team = project.team.filter(id=user.id).exists()
        if not (is_coord or is_mentor or is_team or user.is_staff):
            raise PermissionDenied("You do not have permission to modify this milestone.")

        new_status = serializer.validated_data.get('status')
        if new_status in [ProjectMilestone.Status.APPROVED, ProjectMilestone.Status.CHANGES_REQUESTED] and (is_coord or is_mentor or user.is_staff):
            serializer.validated_data['reviewer'] = user
            serializer.validated_data['reviewed_at'] = timezone.now()

        # If evidence was provided and status was pending/changes_requested, automatically mark as SUBMITTED
        evidence = serializer.validated_data.get('evidence')
        if evidence and milestone.status in [ProjectMilestone.Status.PENDING, ProjectMilestone.Status.IN_PROGRESS, ProjectMilestone.Status.CHANGES_REQUESTED]:
            serializer.validated_data['status'] = ProjectMilestone.Status.SUBMITTED
            serializer.validated_data['submitted_at'] = timezone.now()

        instance = serializer.save()

        # If team submitted milestone, log activity
        if instance.status == ProjectMilestone.Status.SUBMITTED and is_team:
            try:
                log_activity(
                    issue=project.challenge,
                    actor=user,
                    event_type='MILESTONE_SUBMITTED',
                    description=f"Milestone '{instance.title}' submitted for review by {user.name or user.email}",
                    object_type='milestone',
                    object_id=str(instance.id)
                )
            except Exception:
                pass


class ProjectMilestoneReviewView(APIView):
    """
    Mentor/Coordinator approval or changes request for a project milestone (Issue 34).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, project_id, pk):
        project = get_project_by_pk_or_public_id(project_id)
        if not project:
            return Response({'error': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            milestone = ProjectMilestone.objects.get(pk=pk, project_id=project.id)
        except ProjectMilestone.DoesNotExist:
            return Response({'error': 'Milestone not found.'}, status=status.HTTP_404_NOT_FOUND)

        project = milestone.project
        user = request.user
        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == project.university_id)
        is_mentor = (user.id == project.mentor_id)
        if not (is_coord or is_mentor or user.is_staff):
            raise PermissionDenied("Only maintaining university coordinators or assigned faculty mentors can review milestones.")

        action = request.data.get('action')  # 'approve' or 'request_changes'
        feedback = request.data.get('feedback', '')

        if action == 'approve':
            milestone.status = ProjectMilestone.Status.APPROVED
            milestone.reviewed_at = timezone.now()
            milestone.reviewer = user
            if feedback:
                milestone.reviewer_feedback = feedback
            milestone.save()

            # Check if all milestones are approved: advance project status to PILOT if currently planning/prototype
            all_approved = not project.milestones.exclude(status=ProjectMilestone.Status.APPROVED).exists()
            if all_approved and project.status in [Project.Status.PLANNING, Project.Status.PROTOTYPE]:
                project.transition_status(Project.Status.PILOT, actor=user, reason="All intermediate project milestones approved.")

            try:
                log_activity(
                    issue=project.challenge,
                    actor=user,
                    event_type='MILESTONE_APPROVED',
                    description=f"Milestone '{milestone.title}' approved by {user.name or user.email}",
                    object_type='milestone',
                    object_id=str(milestone.id)
                )
            except Exception:
                pass

            return Response({
                'message': f"Milestone '{milestone.title}' approved.",
                'milestone': ProjectMilestoneSerializer(milestone).data,
                'project_status': project.status
            })

        elif action == 'request_changes':
            if not feedback.strip():
                return Response({'error': 'Feedback is required when requesting milestone changes.'}, status=status.HTTP_400_BAD_REQUEST)
            milestone.status = ProjectMilestone.Status.CHANGES_REQUESTED
            milestone.reviewed_at = timezone.now()
            milestone.reviewer = user
            milestone.reviewer_feedback = feedback
            milestone.save()

            try:
                log_activity(
                    issue=project.challenge,
                    actor=user,
                    event_type='MILESTONE_CHANGES_REQUESTED',
                    description=f"Revisions requested for milestone '{milestone.title}': {feedback}",
                    object_type='milestone',
                    object_id=str(milestone.id)
                )
            except Exception:
                pass

            return Response({
                'message': f"Changes requested for milestone '{milestone.title}'.",
                'milestone': ProjectMilestoneSerializer(milestone).data
            })

        return Response({'error': "Invalid action. Use 'approve' or 'request_changes'."}, status=status.HTTP_400_BAD_REQUEST)


# -------------------------------------------------------------------------
# Issue 35: Deployment Gate Views
# -------------------------------------------------------------------------
class ProjectSubmitDeploymentView(APIView):
    """
    Student team submits complete project deployment evidence for review (Issue 35).
    Transitions project to DEPLOYMENT_READY.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        project = get_project_by_pk_or_public_id(pk)
        if not project:
            return Response({'error': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_team = project.team.filter(id=user.id).exists()
        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == project.university_id)
        is_mentor = (user.id == project.mentor_id)
        if not (is_team or is_coord or is_mentor or user.is_staff):
            raise PermissionDenied("Only the project team or coordinator can submit deployment evidence.")

        allowed_source_states = [Project.Status.PILOT, Project.Status.PROTOTYPE]
        if project.status not in allowed_source_states:
            return Response(
                {'error': f'Deployment evidence can only be submitted from Prototype or Pilot status (current status: {project.get_status_display()}).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        evidence = request.data.get('deployment_evidence', '').strip()
        if not evidence:
            return Response({'error': 'Deployment evidence (reports, photos, telemetry, or deliverables) is required.'}, status=status.HTTP_400_BAD_REQUEST)

        outcome = request.data.get('outcome', '').strip()

        with transaction.atomic():
            project = Project.objects.select_for_update().get(pk=project.pk)
            if project.status not in allowed_source_states:
                return Response(
                    {'error': f'Deployment evidence can only be submitted from Prototype or Pilot status (current status: {project.get_status_display()}).'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            project.deployment_evidence = evidence
            extra_fields = ['deployment_evidence']
            if outcome:
                project.outcome = outcome
                extra_fields.append('outcome')
            project.transition_status(
                Project.Status.DEPLOYMENT_READY,
                actor=user,
                reason="Team submitted final deployment package for mentor and coordinator sign-off.",
                extra_update_fields=extra_fields
            )

        return Response({
            'message': 'Deployment package submitted. Pending faculty and university verification.',
            'project': ProjectDetailSerializer(project).data
        })


class ProjectApproveDeploymentView(APIView):
    """
    Mentor/Coordinator verifies evidence and approves field deployment (Issue 35 & C-04).
    Transitions project to DEPLOYED -> AWAITING_CITIZEN_VERIFICATION,
    and transitions underlying challenge Issue to AWAITING_VERIFICATION.
    Direct setting to RESOLVED by students or mentors is forbidden.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        project = get_project_by_pk_or_public_id(pk)
        if not project:
            return Response({'error': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_coord = (getattr(user, 'role', None) == 'university_coordinator' and user.university_id == project.university_id)
        is_mentor = (user.id == project.mentor_id)
        if not (is_coord or is_mentor or user.is_staff):
            raise PermissionDenied("Only university coordinators or assigned faculty mentors can approve deployment.")

        if project.status != Project.Status.DEPLOYMENT_READY:
            return Response(
                {'error': f'Project must be in Deployment Ready status to approve deployment (current status: {project.get_status_display()}).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not project.deployment_evidence or not project.deployment_evidence.strip():
            return Response({'error': 'Cannot approve deployment without submitted deployment evidence.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            project = Project.objects.select_for_update().get(pk=project.pk)
            if project.status != Project.Status.DEPLOYMENT_READY:
                return Response(
                    {'error': f'Project must be in Deployment Ready status to approve deployment (current status: {project.get_status_display()}).'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not project.deployment_evidence or not project.deployment_evidence.strip():
                return Response({'error': 'Cannot approve deployment without submitted deployment evidence.'}, status=status.HTTP_400_BAD_REQUEST)

            # Transition Project: DEPLOYED -> AWAITING_CITIZEN_VERIFICATION
            project.deployment_status = 'deployed'
            project.transition_status(
                Project.Status.DEPLOYED,
                actor=user,
                reason="Faculty mentor and university coordinator verified deployment evidence and approved field pilot.",
                extra_update_fields=['deployment_status']
            )
            project.transition_status(
                Project.Status.AWAITING_CITIZEN_VERIFICATION,
                actor=user,
                reason="Project awaiting field outcome confirmation from original citizen reporter."
            )

            # Transition underlying Challenge Issue to AWAITING_VERIFICATION with row lock
            issue = Issue.objects.select_for_update().get(pk=project.challenge_id)
            issue.transition_status(
                Issue.Status.AWAITING_VERIFICATION,
                actor=user,
                reason=f"Project #{project.id} field deployment approved. Awaiting citizen outcome verification."
            )

        try:
            log_activity(
                issue=issue,
                actor=user,
                event_type='PROJECT_DEPLOYED',
                description=f"Project #{project.id} successfully deployed in field. Citizen verification initiated.",
                object_type='project',
                object_id=str(project.id)
            )
        except Exception:
            pass

        return Response({
            'message': 'Project approved and deployed! Challenge transitioned to Awaiting Verification.',
            'project': ProjectDetailSerializer(project).data,
            'challenge_status': issue.status
        })


class ProjectDiscussionListCreateView(generics.ListCreateAPIView):
    """
    Project-level technical discussions and implementation queries (Section 40 & P1 Issue 40).
    Allows student team, mentor, coordinator, and industry partners to collaborate.
    """
    serializer_class = DiscussionCommentSerializer
    permission_classes = [permissions.IsAuthenticated, ProjectAccessPermission]
    pagination_class = None

    def get_project(self):
        project_id = self.kwargs.get('project_id')
        project = get_project_by_pk_or_public_id(project_id)
        if not project:
            raise NotFound('Project not found.')
        perm = ProjectAccessPermission()
        fake_req = type('Request', (), {'user': self.request.user, 'method': 'GET'})()
        if not perm.has_object_permission(fake_req, self, project):
            raise PermissionDenied('You do not have permission to access discussions for this project.')
        return project

    def get_queryset(self):
        project = self.get_project()
        qs = DiscussionComment.objects.filter(
            project_id=project.id,
            target_type='project'
        ).select_related('author').order_by('created_at')
        cat = self.request.query_params.get('category')
        if cat:
            qs = qs.filter(category=cat.lower())
        return qs

    def perform_create(self, serializer):
        project = self.get_project()
        cat = self.request.data.get('category', 'general')
        comment = serializer.save(
            author=self.request.user,
            project=project,
            issue=project.challenge,
            target_type='project',
            category=cat
        )

        try:
            log_activity(
                issue=project.challenge,
                actor=self.request.user,
                event_type='PROJECT_DISCUSSION',
                description=f"{self.request.user.name or self.request.user.email} commented on Project #{project.id}: {comment.content[:50]}",
                object_type='discussion',
                object_id=str(comment.id),
                metadata={'project_id': project.id}
            )
        except Exception:
            pass


class ProjectStatusHistoryView(APIView):
    """
    Status transition audit log for a project (P1 Issue 39).
    Returns chronological status transition events.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        project = get_project_by_pk_or_public_id(pk)
        if not project:
            return Response({'error': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)

        if request.user and request.user.is_authenticated:
            self.check_object_permissions(request, project)

        events = ActivityEvent.objects.filter(
            issue=project.challenge,
            object_type='project',
            object_id=str(project.id),
            event_type__in=['project_status_changed', 'STATUS_TRANSITION', 'PROJECT_DEPLOYED']
        ).select_related('actor').order_by('-created_at')

        return Response(ActivityEventSerializer(events, many=True).data)


class ProjectExpressInterestView(APIView):
    """
    Allows industry partner to express interest directly in an active project (Issue 51).
    Creates an IndustryEngagement tied directly to the project.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, project_id):
        user = request.user
        if getattr(user, 'role', '') != 'industry_partner' and not user.is_staff:
            return Response({'error': 'Only registered industry partners can express interest in projects.'}, status=status.HTTP_403_FORBIDDEN)
        
        if not user.organization_id and not user.is_staff:
            return Response({'error': 'Industry partner must be affiliated with an organization.'}, status=status.HTTP_400_BAD_REQUEST)

        project = get_project_by_pk_or_public_id(project_id)
        if not project:
            return Response({'error': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)

        engagement_type = request.data.get('engagement_type', IndustryEngagement.EngagementType.MENTORSHIP)
        proposal_notes = request.data.get('proposal_notes', 'Expressed interest in supporting implementation and field pilot.')

        engagement, created = IndustryEngagement.objects.get_or_create(
            project=project,
            industry_org=user.organization,
            defaults={
                'issue': project.challenge,
                'pitch': project.solution,
                'created_by': user,
                'initiator': IndustryEngagement.Initiator.INDUSTRY,
                'engagement_type': engagement_type,
                'proposal_notes': proposal_notes,
                'status': IndustryEngagement.Status.REQUESTED
            }
        )

        try:
            log_activity(
                issue=project.challenge,
                actor=user,
                event_type='INDUSTRY_INTEREST',
                description=f"{user.organization.name if user.organization else user.name} expressed interest in Project #{project.id}: {project.title}",
                object_type='project',
                object_id=str(project.id)
            )
        except Exception:
            pass

        from apps.engagements.serializers import IndustryEngagementSerializer
        return Response(IndustryEngagementSerializer(engagement).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ProjectIndustryEngagementListView(generics.ListAPIView):
    """
    Lists all industry engagements scoped to a specific project (Issue 51).
    """
    permission_classes = [permissions.IsAuthenticated, ProjectAccessPermission]

    def get_serializer_class(self):
        from apps.engagements.serializers import IndustryEngagementSerializer
        return IndustryEngagementSerializer

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        project = get_project_by_pk_or_public_id(project_id)
        if not project:
            raise NotFound('Project not found.')
        self.check_object_permissions(self.request, project)
        return IndustryEngagement.objects.filter(project_id=project.id).select_related('industry_org', 'created_by').order_by('-created_at')


class GenerateCertificateView(APIView):
    """
    Generates verifiable completion/excellence certificate for solution contributors (Issue 55).
    Eligibility:
      1. Winning solution officially selected (Pitch.Status == SELECTED or MERGED)
      2. Project reaches deployment/pilot or verified (Project.Status in [DEPLOYED, VERIFIED, CLOSED])
      3. Deployment evidence approved
      4. Citizen verification completed (Project.Status == VERIFIED or challenge.citizen_verified_resolved == True)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, project_id):
        project = get_project_by_pk_or_public_id(project_id)
        if not project:
            return Response({'error': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_coord = user.role == 'university_coordinator' and user.university_id == project.university_id
        is_mentor = project.mentor_id == user.id
        is_staff = user.is_staff or getattr(user, 'role', '') == 'gov_admin'

        if not (is_coord or is_mentor or is_staff):
            return Response({'error': 'Only the university coordinator, faculty mentor, or government authority can trigger certificate generation.'}, status=status.HTTP_403_FORBIDDEN)

        # Check strict eligibility criteria (Section 55)
        missing_criteria = []
        
        # 1. Solution selected
        if project.solution.status not in [Pitch.Status.SELECTED, Pitch.Status.MERGED]:
            missing_criteria.append("Winning solution must be officially selected.")

        # 2. Project completed / deployed
        if project.status not in [Project.Status.DEPLOYED, Project.Status.VERIFIED, Project.Status.CLOSED]:
            missing_criteria.append("Project must reach deployed or verified status.")

        # 3. Deployment evidence approved
        if not project.deployment_evidence or not project.deployment_evidence.strip():
            missing_criteria.append("Deployment evidence (field photos, reports, or test data) must be provided.")

        # 4. Citizen verification completed
        is_citizen_verified = (
            project.status == Project.Status.VERIFIED or
            bool(project.challenge.citizen_verified_resolved)
        )
        if not is_citizen_verified:
            missing_criteria.append("Citizen verification must be confirmed by the reporting citizen or district.")

        if missing_criteria:
            return Response({
                'error': 'Certificate generation requirements not met.',
                'eligible': False,
                'missing_criteria': missing_criteria
            }, status=status.HTTP_400_BAD_REQUEST)

        # Generate certificates for team members
        certificates_issued = []
        team_members = list(project.team.all())

        for member in team_members:
            cert_id = f"CONF-{project.created_at.year}-{uuid.uuid4().hex[:10].upper()}"
            raw_data = f"{cert_id}:{member.id}:{project.id}:{project.challenge_id}:{project.deployed_at or project.updated_at}"
            verification_hash = hashlib.sha256(raw_data.encode('utf-8')).hexdigest()

            cert, _ = Certificate.objects.get_or_create(
                project=project,
                recipient=member,
                defaults={
                    'certificate_id': cert_id,
                    'challenge': project.challenge,
                    'solution': project.solution,
                    'role': Certificate.Role.STUDENT_INNOVATOR,
                    'title': f"Certificate of Verified Civic Innovation: {project.title}",
                    'verification_hash': verification_hash
                }
            )
            certificates_issued.append(cert)

        # Mentor certificate
        if project.mentor:
            m_cert_id = f"CONF-MENTOR-{project.created_at.year}-{uuid.uuid4().hex[:10].upper()}"
            m_raw = f"{m_cert_id}:{project.mentor.id}:{project.id}:mentor"
            m_hash = hashlib.sha256(m_raw.encode('utf-8')).hexdigest()
            m_cert, _ = Certificate.objects.get_or_create(
                project=project,
                recipient=project.mentor,
                defaults={
                    'certificate_id': m_cert_id,
                    'challenge': project.challenge,
                    'solution': project.solution,
                    'role': Certificate.Role.FACULTY_MENTOR,
                    'title': f"Faculty Mentorship Excellence: {project.title}",
                    'verification_hash': m_hash
                }
            )
            certificates_issued.append(m_cert)

        return Response({
            'message': f"Successfully generated and signed {len(certificates_issued)} verified outcome certificates.",
            'certificates': CertificateSerializer(certificates_issued, many=True).data
        }, status=status.HTTP_201_CREATED)


class VerifyCertificateView(APIView):
    """
    Public verification endpoint for tamper-proof outcome certificates (Issue 55).
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, certificate_id):
        try:
            cert = Certificate.objects.select_related(
                'recipient', 'project', 'challenge', 'solution', 'project__university'
            ).get(certificate_id=certificate_id)
        except Certificate.DoesNotExist:
            return Response({
                'valid': False,
                'error': 'Certificate not found. The ID does not match any authentic Confluence certificate.'
            }, status=status.HTTP_404_NOT_FOUND)

        if cert.is_revoked:
            return Response({
                'valid': False,
                'status': 'revoked',
                'revocation_reason': cert.revocation_reason,
                'certificate_id': cert.certificate_id,
                'recipient_name': cert.recipient.name
            }, status=status.HTTP_200_OK)

        return Response({
            'valid': True,
            'is_valid': True,
            'status': 'authentic',
            'certificate': CertificateSerializer(cert).data,
            'verification': {
                'algorithm': 'SHA-256',
                'hash': cert.verification_hash,
                'verified_outcome': True,
                'citizen_verified': cert.project.challenge.citizen_verified_resolved or cert.project.status == Project.Status.VERIFIED
            }
        }, status=status.HTTP_200_OK)


class UserCertificateListView(generics.ListAPIView):
    """
    Lists all verified outcome certificates awarded to the authenticated user (Issue 55 / H-06).
    """
    serializer_class = CertificateSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return Certificate.objects.filter(
            recipient=self.request.user
        ).select_related(
            'recipient', 'project', 'challenge', 'solution', 'project__university'
        ).order_by('-issued_at')




