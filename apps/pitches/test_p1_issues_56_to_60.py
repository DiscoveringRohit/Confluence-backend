from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.users.models import University
from apps.issues.models import (
    Issue,
    StudentNomination,
    Adoption,
    ChallengeNomination,
    ChallengeAdoption,
)
from apps.issues.serializers import (
    IssueSerializer,
    StudentNominationSerializer,
    AdoptionSerializer,
    ChallengeNominationSerializer,
    ChallengeAdoptionSerializer,
)
from apps.pitches.models import Pitch, Project
from apps.pitches.serializers import PitchSerializer, ProjectSerializer

User = get_user_model()


class TestIssues56To60(TestCase):
    """
    Test suite for Gap Analysis Issues 56 to 60:
    - Issue 56: Repository URL Structure & Canonical Deep-Links
    - Issue 57: Human-Readable Public IDs (CH-00042, SOL-0012, PRJ-0042)
    - Issue 58: Recommended Core Data Model - Challenge (Issue)
    - Issue 59: Challenge Nomination Core Data Model
    - Issue 60: Challenge Adoption Core Data Model
    """

    def setUp(self):
        self.client = APIClient()
        self.university = University.objects.create(
            name="Ranchi Technological University",
            code="RTU-01",
            district="Ranchi"
        )
        self.citizen = User.objects.create_user(
            email="citizen_rep@example.com",
            password="Password@123",
            role="citizen",
            name="Citizen Ramesh"
        )
        self.coordinator = User.objects.create_user(
            email="coord_rtu@example.com",
            password="Password@123",
            role="university_coordinator",
            name="Dr. Verma",
            university=self.university
        )
        self.student = User.objects.create_user(
            email="student_neha@example.com",
            password="Password@123",
            role="student",
            name="Neha Student",
            university=self.university
        )
        self.gov_admin = User.objects.create_user(
            email="gov_officer@example.com",
            password="Password@123",
            role="gov_admin",
            name="Officer Singh"
        )

        self.challenge = Issue.objects.create(
            title="Arsenic in Drinking Water - Ward 4",
            description="Contaminated aquifer exceeding WHO toxicity thresholds.",
            context="Rural borehole supply installed in 2018 with elevated arsenic contamination.",
            expected_outcome="Community filtration plant providing potable water below 10 ppb.",
            requirements="Low-cost chemical filtration matrix, solar-powered flow meters.",
            constraints="Zero grid power availability, high humidity, local panchayat maintenance.",
            acceptance_criteria="Arsenic < 0.01 mg/L verified by local health clinic tests.",
            latitude=23.344100,
            longitude=85.309560,
            district="Ranchi",
            address="Ward 4 Community Well, Kanke",
            category=Issue.Category.WATER,
            status=Issue.Status.VALIDATED,
            submitted_by=self.citizen,
            validated_by=self.gov_admin,
            photo_url="https://example.com/arsenic_well.jpg"
        )

    # -------------------------------------------------------------------------
    # Issue 57 & 58: Public ID Generation & Challenge Data Model Specification
    # -------------------------------------------------------------------------
    def test_challenge_public_id_auto_generation(self):
        """Verify Issue auto-populates deterministic public_id formatted as CH-{id:05d}."""
        self.assertTrue(self.challenge.public_id.startswith("CH-"))
        expected_public_id = f"CH-{self.challenge.id:05d}"
        self.assertEqual(self.challenge.public_id, expected_public_id)

    def test_challenge_core_data_model_specification(self):
        """Verify all Section 58 Challenge specification fields and properties."""
        c = self.challenge
        self.assertIsNotNone(c.id)
        self.assertIsNotNone(c.public_id)
        self.assertEqual(c.created_by, self.citizen)
        self.assertEqual(c.title, "Arsenic in Drinking Water - Ward 4")
        self.assertIn("Contaminated aquifer", c.description)
        self.assertEqual(c.context, "Rural borehole supply installed in 2018 with elevated arsenic contamination.")
        self.assertEqual(c.expected_outcome, "Community filtration plant providing potable water below 10 ppb.")
        self.assertEqual(c.requirements, "Low-cost chemical filtration matrix, solar-powered flow meters.")
        self.assertEqual(c.constraints, "Zero grid power availability, high humidity, local panchayat maintenance.")
        self.assertEqual(c.acceptance_criteria, "Arsenic < 0.01 mg/L verified by local health clinic tests.")
        self.assertEqual(c.category, Issue.Category.WATER)
        self.assertEqual(c.status, Issue.Status.VALIDATED)
        self.assertIsNone(c.maintainer_university)
        self.assertIsNotNone(c.created_at)
        self.assertIsNotNone(c.updated_at)

        # Structured location dictionary
        loc = c.location
        self.assertEqual(loc['district'], "Ranchi")
        self.assertEqual(loc['address'], "Ward 4 Community Well, Kanke")
        self.assertAlmostEqual(loc['latitude'], 23.344100)
        self.assertAlmostEqual(loc['longitude'], 85.309560)

    def test_challenge_serializer_exposes_specification_fields(self):
        """Verify IssueSerializer exposes all required Section 58 fields."""
        serializer = IssueSerializer(self.challenge)
        data = serializer.data
        self.assertEqual(data['public_id'], self.challenge.public_id)
        self.assertEqual(data['context'], self.challenge.context)
        self.assertEqual(data['requirements'], self.challenge.requirements)
        self.assertEqual(data['constraints'], self.challenge.constraints)
        self.assertEqual(data['created_by'], self.citizen.id)
        self.assertIsInstance(data['location'], dict)
        self.assertEqual(data['location']['district'], "Ranchi")

    # -------------------------------------------------------------------------
    # Issue 57: Solution & Project Public IDs (SOL-0012, PRJ-0042)
    # -------------------------------------------------------------------------
    def test_solution_and_project_public_id_auto_generation(self):
        """Verify Pitch and Project auto-generate SOL-{id:04d} and PRJ-{id:04d} identifiers."""
        # Adopt challenge
        adoption = Adoption.objects.create(
            issue=self.challenge,
            university=self.university,
            coordinator=self.coordinator,
            status=Adoption.Status.APPROVED
        )
        self.challenge.status = Issue.Status.ADOPTED
        self.challenge.maintaining_university = self.university
        self.challenge.save()

        pitch = Pitch.objects.create(
            issue=self.challenge,
            university=self.university,
            title="Electro-Coagulation Filter Prototype",
            public_summary="Solar-powered electro-coagulation for arsenic precipitation.",
            confidential_package="Anode cathode specs and pulse frequency circuitry.",
            status=Pitch.Status.SELECTED
        )
        self.assertTrue(pitch.public_id.startswith("SOL-"))
        self.assertEqual(pitch.public_id, f"SOL-{pitch.id:04d}")

        project = Project.objects.create(
            solution=pitch,
            challenge=self.challenge,
            university=self.university,
            title="Field Pilot - Ward 4 Filter",
            status=Project.Status.PLANNING
        )
        self.assertTrue(project.public_id.startswith("PRJ-"))
        self.assertEqual(project.public_id, f"PRJ-{project.id:04d}")

        # Test serializer inclusion
        pitch_data = PitchSerializer(pitch).data
        self.assertEqual(pitch_data['public_id'], pitch.public_id)

        proj_data = ProjectSerializer(project).data
        self.assertEqual(proj_data['public_id'], project.public_id)
        self.assertEqual(proj_data['solution_details']['public_id'], pitch.public_id)
        self.assertEqual(proj_data['challenge_details']['public_id'], self.challenge.public_id)

    # -------------------------------------------------------------------------
    # Issue 56 & 57: Dual ID Resolution (Integer PK & Public ID) in Detail Views
    # -------------------------------------------------------------------------
    def test_challenge_detail_view_dual_resolution(self):
        """Verify GET /api/issues/{pk}/ resolves using both integer ID and public_id."""
        self.client.force_authenticate(user=self.citizen)

        # 1. By numeric primary key
        res_numeric = self.client.get(f"/api/issues/{self.challenge.id}/")
        self.assertEqual(res_numeric.status_code, status.HTTP_200_OK)
        self.assertEqual(res_numeric.data['id'], self.challenge.id)

        # 2. By public_id (e.g. CH-00001)
        res_public = self.client.get(f"/api/issues/{self.challenge.public_id}/")
        self.assertEqual(res_public.status_code, status.HTTP_200_OK)
        self.assertEqual(res_public.data['public_id'], self.challenge.public_id)
        self.assertEqual(res_public.data['id'], self.challenge.id)

    def test_solution_and_project_detail_view_dual_resolution(self):
        """Verify Pitch and Project Detail views resolve using numeric ID or public_id."""
        Adoption.objects.create(
            issue=self.challenge,
            university=self.university,
            coordinator=self.coordinator,
            status=Adoption.Status.APPROVED
        )
        self.challenge.status = Issue.Status.ADOPTED
        self.challenge.save()

        pitch = Pitch.objects.create(
            issue=self.challenge,
            university=self.university,
            title="Bio-Sand Biochar Adsorbent",
            public_summary="Locally sourced biochar adsorption bed.",
            confidential_package="Pyrolysis temp and surface acid activation curves."
        )
        pitch.student_team.add(self.student)

        project = Project.objects.create(
            solution=pitch,
            challenge=self.challenge,
            university=self.university,
            title="Biochar Pilot Implementation"
        )
        project.team.add(self.student)

        self.client.force_authenticate(user=self.student)

        # Solution numeric lookup
        res_sol_num = self.client.get(f"/api/pitches/{pitch.id}/")
        self.assertEqual(res_sol_num.status_code, status.HTTP_200_OK)
        self.assertEqual(res_sol_num.data['id'], pitch.id)

        # Solution public_id lookup (e.g. SOL-0001)
        res_sol_pub = self.client.get(f"/api/pitches/{pitch.public_id}/")
        self.assertEqual(res_sol_pub.status_code, status.HTTP_200_OK)
        self.assertEqual(res_sol_pub.data['public_id'], pitch.public_id)

        # Project numeric lookup
        res_prj_num = self.client.get(f"/api/pitches/projects/{project.id}/")
        self.assertEqual(res_prj_num.status_code, status.HTTP_200_OK)
        self.assertEqual(res_prj_num.data['id'], project.id)

        # Project public_id lookup (e.g. PRJ-0001)
        res_prj_pub = self.client.get(f"/api/pitches/projects/{project.public_id}/")
        self.assertEqual(res_prj_pub.status_code, status.HTTP_200_OK)
        self.assertEqual(res_prj_pub.data['public_id'], project.public_id)

    # -------------------------------------------------------------------------
    # Issue 59: Challenge Nomination Core Data Model
    # -------------------------------------------------------------------------
    def test_challenge_nomination_data_model_and_alias(self):
        """Verify Section 59 ChallengeNomination data model, aliases, and properties."""
        self.assertIs(ChallengeNomination, StudentNomination)
        self.assertIs(ChallengeNominationSerializer, StudentNominationSerializer)

        nomination = ChallengeNomination.objects.create(
            issue=self.challenge,
            student=self.student,
            university=self.university,
            rationale="Our department has a water filtration research lab dedicated to arsenic mitigation."
        )

        # Property 'challenge' aliases 'issue'
        self.assertEqual(nomination.challenge, self.challenge)
        self.assertEqual(nomination.student, self.student)
        self.assertEqual(nomination.university, self.university)
        self.assertEqual(nomination.status, StudentNomination.Status.PENDING)
        self.assertIsNotNone(nomination.created_at)
        self.assertIsNone(nomination.reviewed_at)

        # Setter works
        nomination.challenge = self.challenge
        self.assertEqual(nomination.issue, self.challenge)

        # Serializer exposes challenge alias
        data = ChallengeNominationSerializer(nomination).data
        self.assertEqual(data['challenge'], self.challenge.id)
        self.assertEqual(data['issue'], self.challenge.id)

    # -------------------------------------------------------------------------
    # Issue 60: Challenge Adoption Core Data Model
    # -------------------------------------------------------------------------
    def test_challenge_adoption_data_model_and_approved_at(self):
        """Verify Section 60 ChallengeAdoption data model, approved_at auto-stamping, and properties."""
        self.assertIs(ChallengeAdoption, Adoption)
        self.assertIs(ChallengeAdoptionSerializer, AdoptionSerializer)

        adoption = ChallengeAdoption.objects.create(
            issue=self.challenge,
            university=self.university,
            coordinator=self.coordinator,
            nominated_by=self.student,
            status=Adoption.Status.APPROVED
        )

        # Property 'challenge' aliases 'issue'
        self.assertEqual(adoption.challenge, self.challenge)
        self.assertEqual(adoption.university, self.university)
        self.assertEqual(adoption.coordinator, self.coordinator)
        self.assertEqual(adoption.nominated_by, self.student)
        self.assertEqual(adoption.status, Adoption.Status.APPROVED)
        self.assertIsNotNone(adoption.created_at)
        # approved_at auto-stamped when status is APPROVED
        self.assertIsNotNone(adoption.approved_at)

        # Serializer includes challenge, created_at, and approved_at
        data = ChallengeAdoptionSerializer(adoption).data
        self.assertEqual(data['challenge'], self.challenge.id)
        self.assertIsNotNone(data['created_at'])
        self.assertIsNotNone(data['approved_at'])

    def test_challenge_adoption_approved_at_on_transition(self):
        """Verify approved_at is stamped when an adoption transitions to approved."""
        adoption = ChallengeAdoption.objects.create(
            issue=self.challenge,
            university=self.university,
            coordinator=self.coordinator,
            status=Adoption.Status.REQUESTED
        )
        self.assertIsNone(adoption.approved_at)

        # Transition to approved
        adoption.status = Adoption.Status.APPROVED
        adoption.save()
        self.assertIsNotNone(adoption.approved_at)

    def test_subpaths_resolve_with_public_id(self):
        """Verify issue activity timeline, status history, and discussions resolve with public_id."""
        self.client.force_authenticate(user=self.citizen)

        # Activity timeline with public_id
        res_act = self.client.get(f"/api/issues/{self.challenge.public_id}/activity/")
        self.assertEqual(res_act.status_code, status.HTTP_200_OK)

        # Status history with public_id
        res_hist = self.client.get(f"/api/issues/{self.challenge.public_id}/status-history/")
        self.assertEqual(res_hist.status_code, status.HTTP_200_OK)

        # Discussions with public_id
        res_disc = self.client.get(f"/api/issues/{self.challenge.public_id}/discussions/")
        self.assertEqual(res_disc.status_code, status.HTTP_200_OK)
