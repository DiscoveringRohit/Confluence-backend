import requests
from django.utils import timezone
from django.conf import settings
from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Issue, Adoption, StudentNomination
from .serializers import (
    IssueSerializer,
    IssueModerationSerializer,
    AdoptionSerializer,
    StudentNominationSerializer,
)
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
        payload = {
            "title": issue.title,
            "description": issue.description,
            "district": issue.district,
        }
        res = requests.post(url, json=payload, timeout=3)
        if res.status_code == 200:
            data = res.json()
            issue.category = data.get('predicted_category', issue.category)
            issue.ai_confidence = data.get('confidence', 0.85)
            issue.ai_triage_notes = data.get('summary', 'AI classification applied')
            if data.get('potential_duplicate_id'):
                try:
                    dup = Issue.objects.get(id=data['potential_duplicate_id'])
                    issue.ai_triage_notes += f" | Flagged duplicate of #{dup.id}"
                except Issue.DoesNotExist:
                    pass
            issue.save(update_fields=['category', 'ai_confidence', 'ai_triage_notes'])
            return
    except Exception:
        pass

    # Heuristic fallback if AI service is not running
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


class IssueListCreateView(generics.ListCreateAPIView):
    serializer_class = IssueSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description', 'district', 'address']

    def get_queryset(self):
        qs = Issue.objects.select_related('submitted_by', 'adoption', 'adoption__university', 'duplicate_of').all().order_by('-created_at')
        
        status_param = self.request.query_params.get('status')
        category_param = self.request.query_params.get('category')
        district_param = self.request.query_params.get('district')
        mine_param = self.request.query_params.get('mine')

        if status_param:
            qs = qs.filter(status=status_param)
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
        run_ai_triage(issue)


class IssueDetailView(generics.RetrieveUpdateAPIView):
    queryset = Issue.objects.select_related('submitted_by', 'adoption', 'adoption__university').all()
    serializer_class = IssueSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class IssueModerationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ['gov_admin', 'university_coordinator'] and not request.user.is_staff:
            raise PermissionDenied("Only moderators/admins can validate issues.")

        try:
            issue = Issue.objects.get(pk=pk)
        except Issue.DoesNotExist:
            return Response({'error': 'Issue not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = IssueModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']

        if action == 'validate':
            issue.status = Issue.Status.VALIDATED
            if 'category' in serializer.validated_data:
                issue.category = serializer.validated_data['category']
            issue.save()
            return Response({'message': 'Issue validated and published to public board.', 'status': issue.status})

        elif action == 'reject':
            issue.status = 'rejected'
            issue.save()
            return Response({'message': 'Issue rejected.', 'status': issue.status})

        elif action == 'mark_duplicate':
            dup_id = serializer.validated_data.get('duplicate_of_id')
            if not dup_id:
                return Response({'error': 'duplicate_of_id required'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                parent = Issue.objects.get(pk=dup_id)
                issue.duplicate_of = parent
                issue.save()
                return Response({'message': f'Issue marked as duplicate of #{parent.id}'})
            except Issue.DoesNotExist:
                return Response({'error': 'Target duplicate issue does not exist'}, status=status.HTTP_404_NOT_FOUND)


class AdoptIssueView(APIView):
    """
    University coordinator adopts a validated issue directly.
    """
    permission_classes = [permissions.IsAuthenticated, IsUniversityCoordinator]

    def post(self, request, pk):
        try:
            issue = Issue.objects.get(pk=pk)
        except Issue.DoesNotExist:
            return Response({'error': 'Issue not found'}, status=status.HTTP_404_NOT_FOUND)

        if issue.status != Issue.Status.VALIDATED:
            return Response({'error': f'Issue cannot be adopted because status is {issue.status}'}, status=status.HTTP_400_BAD_REQUEST)

        university = request.user.university
        if not university:
            return Response({'error': 'User is not affiliated with any university.'}, status=status.HTTP_400_BAD_REQUEST)

        if hasattr(issue, 'adoption'):
            return Response({'error': 'Issue is already adopted.'}, status=status.HTTP_400_BAD_REQUEST)

        adoption = Adoption.objects.create(
            issue=issue,
            university=university,
            mode=Adoption.Mode.SELF_ADOPTED
        )
        issue.status = Issue.Status.ADOPTED
        issue.save(update_fields=['status'])

        return Response(AdoptionSerializer(adoption).data, status=status.HTTP_201_CREATED)


class NominateIssueView(APIView):
    """
    Student nominates an unclaimed issue for their university to adopt.
    """
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request, pk):
        try:
            issue = Issue.objects.get(pk=pk)
        except Issue.DoesNotExist:
            return Response({'error': 'Issue not found'}, status=status.HTTP_404_NOT_FOUND)

        if issue.status != Issue.Status.VALIDATED:
            return Response({'error': 'Only unadopted, validated issues can be nominated.'}, status=status.HTTP_400_BAD_REQUEST)

        university = request.user.university
        if not university:
            return Response({'error': 'Student must be affiliated with a university.'}, status=status.HTTP_400_BAD_REQUEST)

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
                    'mode': Adoption.Mode.NOMINATION_APPROVED,
                    'nominated_by': nomination.student
                }
            )
            issue.status = Issue.Status.ADOPTED
            issue.save(update_fields=['status'])

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
    """List nominations for the coordinator's university."""
    serializer_class = StudentNominationSerializer
    permission_classes = [permissions.IsAuthenticated, IsUniversityCoordinator]

    def get_queryset(self):
        return StudentNomination.objects.filter(
            university=self.request.user.university,
            status=StudentNomination.Status.PENDING
        ).order_by('-created_at')


class CitizenConfirmResolutionView(APIView):
    """
    Close the loop with the citizen: lets the original submitter confirm whether
    the deployed solution resolved the societal issue.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            issue = Issue.objects.get(pk=pk)
        except Issue.DoesNotExist:
            return Response({'error': 'Issue not found'}, status=status.HTTP_404_NOT_FOUND)

        if issue.submitted_by != request.user and not request.user.is_staff:
            raise PermissionDenied("Only the original submitter can confirm resolution.")

        is_confirmed = request.data.get('confirmed', True)
        feedback = request.data.get('feedback', '')

        issue.citizen_verified_resolved = is_confirmed
        issue.citizen_feedback_on_resolution = feedback
        issue.save(update_fields=['citizen_verified_resolved', 'citizen_feedback_on_resolution'])

        return Response({
            'message': 'Citizen resolution feedback recorded.',
            'citizen_verified_resolved': issue.citizen_verified_resolved,
            'citizen_feedback_on_resolution': issue.citizen_feedback_on_resolution
        })
