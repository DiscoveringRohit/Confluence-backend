from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.users.models import User, University
from apps.issues.models import Issue, Adoption, StudentNomination
from apps.pitches.models import (
    Pitch, PitchVersionHistory, SolutionTeamMember, ProjectLifecycle
)


class P1Issues21To25TestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Universities
        self.uni_a = University.objects.create(name="BIT Sindri", district="Dhanbad")
        self.uni_b = University.objects.create(name="Ranchi University", district="Ranchi")

        # Users
        self.citizen = User.objects.create_user(
            email="citizen_21@jharkhand.in",
            name="Citizen Birsa",
            role=User.Role.CITIZEN
        )
        self.coord_a = User.objects.create_user(
            email="coord_a@bitsindri.ac.in",
            name="Coordinator BIT",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_a
        )
        self.coord_b = User.objects.create_user(
            email="coord_b@ranchi.ac.in",
            name="Coordinator RU",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_b
        )
        self.student_lead = User.objects.create_user(
            email="lead_21@bitsindri.ac.in",
            name="Student Lead",
            role=User.Role.STUDENT,
            university=self.uni_a
        )
        self.student_dev = User.objects.create_user(
            email="dev_21@bitsindri.ac.in",
            name="Student Dev",
            role=User.Role.STUDENT,
            university=self.uni_a
        )
        self.student_designer = User.objects.create_user(
            email="designer_21@bitsindri.ac.in",
            name="Student Designer",
            role=User.Role.STUDENT,
            university=self.uni_a
        )
        self.student_other_uni = User.objects.create_user(
            email="other_uni@ranchi.ac.in",
            name="Student RU",
            role=User.Role.STUDENT,
            university=self.uni_b
        )

        # Adopted Issue
        self.issue = Issue.objects.create(
            title="Solar Micro-Grid for Rural Jharia",
            description="Intermittent electricity in rural hamlets.",
            category="energy",
            district="Dhanbad",
            submitted_by=self.citizen,
            status=Issue.Status.ADOPTED
        )
        self.adoption = Adoption.objects.create(
            issue=self.issue,
            university=self.uni_a,
            coordinator=self.coord_a
        )

        # Pitch
        self.pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.uni_a,
            title="DC Microgrid with Smart Battery Management",
            public_summary="Decentralized solar charging hubs.",
            confidential_package="Install 5kW rooftop arrays with IoT metering and telemetry algorithms.",
            repository_url="https://github.com/bitsindri/solar-iot",
            demo_url="https://solar-demo.bitsindri.ac.in",
            documentation_url="https://docs.solar.bitsindri.ac.in",
            video_url="https://youtube.com/watch?v=sample123",
            status=Pitch.Status.SUBMITTED
        )
        self.pitch.student_team.add(self.student_lead)

        # Add student_lead as OWNER in SolutionTeamMember
        SolutionTeamMember.objects.create(
            pitch=self.pitch,
            student=self.student_lead,
            role=SolutionTeamMember.Role.OWNER,
            status=SolutionTeamMember.Status.ACTIVE
        )

    # --- Issue 21: GitHub / Repository Links & Version Tracking ---
    def test_repository_links_storage_and_versioning(self):
        """Test that repository, demo, documentation, and video URLs are tracked and saved in version history."""
        self.assertEqual(self.pitch.repository_url, "https://github.com/bitsindri/solar-iot")
        self.assertEqual(self.pitch.demo_url, "https://solar-demo.bitsindri.ac.in")
        self.assertEqual(self.pitch.documentation_url, "https://docs.solar.bitsindri.ac.in")
        self.assertEqual(self.pitch.video_url, "https://youtube.com/watch?v=sample123")

        # Now update pitch with new repository URL and track history
        self.client.force_authenticate(user=self.student_lead)
        response = self.client.patch(f"/api/pitches/{self.pitch.id}/", {
            "repository_url": "https://github.com/bitsindri/solar-iot-v2",
            "demo_url": "https://solar-demo-v2.bitsindri.ac.in",
            "version_notes": "Added live battery telemetry dashboard"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.pitch.refresh_from_db()
        self.assertEqual(self.pitch.repository_url, "https://github.com/bitsindri/solar-iot-v2")
        self.assertEqual(self.pitch.version, 2)

        # Check version history entry
        versions = PitchVersionHistory.objects.filter(pitch=self.pitch)
        self.assertEqual(versions.count(), 1)
        v1 = versions.first()
        self.assertEqual(v1.version, 1)
        self.assertEqual(v1.repository_url, "https://github.com/bitsindri/solar-iot")
        self.assertEqual(v1.demo_url, "https://solar-demo.bitsindri.ac.in")

    # --- Issue 22: Student Team Model ---
    def test_team_member_creation_and_roles(self):
        """Test creating structured team members with varied roles and statuses."""
        member = SolutionTeamMember.objects.create(
            pitch=self.pitch,
            student=self.student_dev,
            role=SolutionTeamMember.Role.DEVELOPER,
            status=SolutionTeamMember.Status.ACTIVE
        )
        self.assertEqual(member.role, "developer")
        self.assertEqual(member.status, "active")
        self.assertIn("Core Developer / Engineer", str(member))

    # --- Issue 23: Team Authorization & University Verification ---
    def test_add_team_member_success_by_owner(self):
        """Pitch owner can add a fellow student from the same university."""
        self.client.force_authenticate(user=self.student_lead)
        response = self.client.post(f"/api/pitches/{self.pitch.id}/team/", {
            "user_id": str(self.student_dev.id),
            "role": "DEVELOPER"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "developer")
        self.assertEqual(response.data["student_details"]["email"], "dev_21@bitsindri.ac.in")

    def test_add_team_member_from_different_university_rejected(self):
        """Adding a student from a different university is rejected with 400."""
        self.client.force_authenticate(user=self.student_lead)
        response = self.client.post(f"/api/pitches/{self.pitch.id}/team/", {
            "user_id": str(self.student_other_uni.id),
            "role": "DEVELOPER"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("must be enrolled at the same university", response.data["error"])

    def test_add_non_student_to_team_rejected(self):
        """Adding a citizen or non-student user to student team is rejected."""
        self.client.force_authenticate(user=self.student_lead)
        response = self.client.post(f"/api/pitches/{self.pitch.id}/team/", {
            "user_id": str(self.citizen.id),
            "role": "RESEARCHER"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Only students can be added", response.data["error"])

    def test_duplicate_team_member_rejected(self):
        """Cannot add the same user twice to a solution team."""
        self.client.force_authenticate(user=self.student_lead)
        # student_lead is already owner
        response = self.client.post(f"/api/pitches/{self.pitch.id}/team/", {
            "user_id": str(self.student_lead.id),
            "role": "DEVELOPER"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already a member", response.data["error"])

    def test_unauthorized_user_cannot_manage_team(self):
        """An unrelated student cannot add members to another student's pitch."""
        self.client.force_authenticate(user=self.student_dev)
        response = self.client.post(f"/api/pitches/{self.pitch.id}/team/", {
            "user_id": str(self.student_designer.id),
            "role": "DESIGNER"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sole_owner_removal_protection(self):
        """Cannot remove the sole OWNER of a pitch."""
        owner_member = SolutionTeamMember.objects.get(pitch=self.pitch, student=self.student_lead)
        self.client.force_authenticate(user=self.student_lead)
        response = self.client.delete(f"/api/pitches/{self.pitch.id}/team/{owner_member.id}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot remove the sole owner", response.data["error"])

    def test_coordinator_can_remove_team_member(self):
        """University coordinator has authority to remove team members."""
        member = SolutionTeamMember.objects.create(
            pitch=self.pitch,
            student=self.student_dev,
            role=SolutionTeamMember.Role.DEVELOPER,
            status=SolutionTeamMember.Status.ACTIVE
        )
        self.client.force_authenticate(user=self.coord_a)
        response = self.client.delete(f"/api/pitches/{self.pitch.id}/team/{member.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        member.refresh_from_db()
        self.assertEqual(member.status, SolutionTeamMember.Status.REMOVED)
        self.assertFalse(self.pitch.student_team.filter(id=self.student_dev.id).exists())

    # --- Issue 24 & 25: Action Inbox View ---
    def test_university_action_inbox_requires_coordinator_or_mentor(self):
        """Citizens and unauthorized students cannot access the university action inbox."""
        self.client.force_authenticate(user=self.citizen)
        response = self.client.get("/api/issues/action-inbox/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.student_lead)
        response = self.client.get("/api/issues/action-inbox/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_university_action_inbox_aggregates_all_5_buckets(self):
        """Action Inbox returns total count and breakdown for all 5 required buckets."""
        # 1. Challenge awaiting review (SUBMITTED status in coordinator's district)
        review_issue = Issue.objects.create(
            title="Broken Culvert in Govindpur",
            description="Drainage culvert blocked causing flooding.",
            category="infrastructure",
            district="Dhanbad",
            submitted_by=self.citizen,
            status=Issue.Status.SUBMITTED
        )

        # 2. Student nomination awaiting decision
        nomination = StudentNomination.objects.create(
            issue=self.issue,
            student=self.student_dev,
            university=self.uni_a,
            rationale="Experienced in embedded solar controllers.",
            status=StudentNomination.Status.PENDING
        )

        # 3. Solutions awaiting review (self.pitch is SUBMITTED)

        # 4. Milestones awaiting approval
        lifecycle = ProjectLifecycle.objects.create(
            pitch=self.pitch,
            outcome_status=ProjectLifecycle.OutcomeStatus.IN_PROGRESS,
            milestones=[
                {
                    "title": "Battery Lab Testing",
                    "due_date": "2026-10-01",
                    "status": "pending_approval"
                }
            ]
        )

        # 5. Citizen verification failure (REOPENED issue)
        disputed_issue = Issue.objects.create(
            title="Water Tap Leakage at Chas",
            description="Tap was reported fixed but water is still contaminated.",
            category="water_sanitation",
            district="Dhanbad",
            submitted_by=self.citizen,
            status=Issue.Status.REOPENED
        )

        self.client.force_authenticate(user=self.coord_a)
        response = self.client.get("/api/issues/action-inbox/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertIn("total_pending_actions", data)
        self.assertIn("buckets", data)

        buckets = data["buckets"]
        # Check all 5 buckets exist
        self.assertIn("challenges_awaiting_review", buckets)
        self.assertIn("nominations_awaiting_decision", buckets)
        self.assertIn("solutions_awaiting_review", buckets)
        self.assertIn("milestones_awaiting_approval", buckets)
        self.assertIn("citizen_verification_failures", buckets)

        # Check counts
        self.assertGreaterEqual(buckets["challenges_awaiting_review"]["count"], 1)
        self.assertGreaterEqual(buckets["nominations_awaiting_decision"]["count"], 1)
        self.assertGreaterEqual(buckets["solutions_awaiting_review"]["count"], 1)
        self.assertGreaterEqual(buckets["milestones_awaiting_approval"]["count"], 1)
        self.assertGreaterEqual(buckets["citizen_verification_failures"]["count"], 1)

        self.assertGreaterEqual(data["total_pending_actions"], 5)
