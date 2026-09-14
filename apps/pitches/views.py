from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Pitch, CommunityFeedback, ProjectLifecycle
from .serializers import (
    PitchSerializer,
    PitchCreateSerializer,
    CommunityFeedbackSerializer,
    ProjectLifecycleSerializer,
    ReviewBoardActionSerializer,
)
from apps.issues.models import Issue
from apps.users.models import User
from apps.engagements.models import IndustryEngagement
from apps.users.permissions import (
    IsStudent,
    IsUniversityCoordinator,
    IsFacultyMentor,
    IsUniversityAffiliated,
    IsCitizen,
)

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
            qs = qs.filter(issue_id=issue_id)
        if mine and self.request.user.is_authenticated:
            qs = qs.filter(student_team=self.request.user)
        if uni_id:
            qs = qs.filter(university_id=uni_id)
        elif self.request.user.is_authenticated and getattr(self.request.user, 'role', None) == 'university_coordinator':
            # Coordinators default to seeing their own university's pitches
            if self.request.user.university_id:
                qs = qs.filter(university_id=self.request.user.university_id)

        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated or user.role != 'student':
            raise PermissionDenied("Only authenticated students can submit pitches.")
        
        issue = serializer.validated_data['issue']
        if issue.status != Issue.Status.ADOPTED:
            raise ValidationError("Pitches can only be submitted for adopted issues (open calls).")
        
        serializer.save()


class PitchDetailView(generics.RetrieveAPIView):
    queryset = Pitch.objects.select_related('issue', 'university', 'assigned_mentor').prefetch_related('student_team', 'community_feedback').all()
    serializer_class = PitchSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


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
        try:
            pitch = Pitch.objects.get(pk=pitch_id)
        except Pitch.DoesNotExist:
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


class ReviewBoardActionView(APIView):
    """
    University Review Board:
    - Compare all submitted pitches together
    - Select one pitch outright
    - Merge two complementary pitches into one joint team
    - Assign faculty mentor
    """
    permission_classes = [permissions.IsAuthenticated, IsUniversityCoordinator]

    def post(self, request, pk):
        try:
            pitch = Pitch.objects.get(pk=pk, university=request.user.university)
        except Pitch.DoesNotExist:
            return Response({'error': 'Pitch not found for your university.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReviewBoardActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        action = data['action']

        if action == 'reject':
            # Early rejection: discard a weak pitch before a winner has been chosen.
            # This does NOT transition the issue status — the open call remains active.
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
            mentor_id = data.get('mentor_id')
            try:
                mentor = User.objects.get(pk=mentor_id, role='faculty_mentor')
                pitch.assigned_mentor = mentor
                pitch.save(update_fields=['assigned_mentor'])
                return Response({'message': f'Mentor {mentor.name} assigned to pitch.'})
            except User.DoesNotExist:
                return Response({'error': 'Valid faculty mentor required.'}, status=status.HTTP_400_BAD_REQUEST)

        elif action == 'select_winner':
            pitch.status = Pitch.Status.SELECTED
            pitch.review_feedback = data.get('review_feedback', 'Selected as winning solution by University Review Board.')
            pitch.save(update_fields=['status', 'review_feedback'])

            # Transition issue to 'assigned'
            issue = pitch.issue
            issue.status = Issue.Status.ASSIGNED
            issue.save(update_fields=['status'])

            # Create or get ProjectLifecycle
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
                'lifecycle': ProjectLifecycleSerializer(lifecycle).data
            })

        elif action == 'merge_pitches':
            merge_with_id = data.get('merge_with_pitch_id')
            if not merge_with_id:
                return Response({'error': 'merge_with_pitch_id is required to merge.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                second_pitch = Pitch.objects.get(pk=merge_with_id, issue=pitch.issue, university=request.user.university)
            except Pitch.DoesNotExist:
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

            # Transition issue
            issue = pitch.issue
            issue.status = Issue.Status.ASSIGNED
            issue.save(update_fields=['status'])

            # Automatically link any active/requested industry engagements for this problem to the primary pitch
            IndustryEngagement.objects.filter(issue=issue, pitch__isnull=True).update(pitch=pitch)

            # Auto-reject any remaining competing pitches on the same issue
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

            return Response({
                'message': f'Pitches #{pitch.id} and #{second_pitch.id} successfully merged into a single collaborative team!',
                'pitch': PitchSerializer(pitch, context={'request': request}).data,
                'lifecycle': ProjectLifecycleSerializer(lifecycle).data
            })

        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


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
                # Also transition issue to 'resolved'
                pitch.issue.status = Issue.Status.RESOLVED
                pitch.issue.save(update_fields=['status'])

        lifecycle.save()
        return Response(ProjectLifecycleSerializer(lifecycle).data)
