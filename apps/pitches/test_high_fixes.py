from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from apps.issues.models import Issue, Adoption, ActivityEvent
from apps.pitches.models import Pitch, Project, Certificate
from apps.engagements.models import IndustryEngagement
from apps.users.models import University, Organization
from portal import settings

User = get_user_model()


class HighFixesTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create University & Organization
        self.univ = University.objects.create(name="Birsa Institute of Technology", district="Dhanbad")
        self.other_univ = University.objects.create(name="National Institute of Technology", district="Jamshedpur")
        self.org = Organization.objects.create(name="Tata Steel Civic Labs", org_type="industry")

        # Users
        self.admin = User.objects.create_superuser(
            email="admin_h@example.com", password="Password123!", role="gov_admin", name="Gov Admin"
        )
        self.coord = User.objects.create_user(
            email="coord_h@example.com", password="Password123!", role="university_coordinator",
            name="Univ Coord", university=self.univ
        )
        self.unassigned_coord = User.objects.create_user(
            email="coord_none@example.com", password="Password123!", role="university_coordinator",
            name="No Univ Coord", university=None
        )
        self.mentor = User.objects.create_user(
            email="mentor_h@example.com", password="Password123!", role="faculty_mentor",
            name="Faculty Mentor", university=self.univ
        )
        self.student_team_lead = User.objects.create_user(
            email="student_team@example.com", password="Password123!", role="student",
            name="Team Lead Student", university=self.univ
        )
        self.student_unrelated = User.objects.create_user(
            email="student_unrelated@example.com", password="Password123!", role="student",
            name="Unrelated Student", university=self.other_univ
        )
        self.citizen = User.objects.create_user(
            email="citizen_h@example.com", password="Password123!", role="citizen",
            name="Citizen Submitter"
        )
        self.industry_user = User.objects.create_user(
            email="industry_h@example.com", password="Password123!", role="industry_partner",
            name="Industry Lead", organization=self.org
        )

        # Issue
        self.issue = Issue.objects.create(
            title="Severe Road Potholes at NH33",
            description="NH33 stretch damaged causing severe accidents",
            expected_outcome="Durable road remediation",
            status=Issue.Status.VALIDATED,
            category=Issue.Category.URBAN_INFRA,
            district="Ranchi",
            submitted_by=self.citizen
        )

        # Solution / Pitch
        self.pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.univ,
            title="Cold-Mix Asphalt Rapid Pothole Patching",
            public_summary="Rapid durable bitumen patching solution",
            status=Pitch.Status.SELECTED,
            assigned_mentor=self.mentor
        )
        self.pitch.student_team.add(self.student_team_lead)

        # Project
        self.project = Project.objects.create(
            challenge=self.issue,
            solution=self.pitch,
            university=self.univ,
            mentor=self.mentor,
            title="NH33 Pothole Repair Pilot",
            status=Project.Status.PILOT
        )
        self.project.team.add(self.student_team_lead)

    # -------------------------------------------------------------
    # H-02 Tests: University Governance & Adoption Integrity
    # -------------------------------------------------------------
    def test_h02_faculty_mentor_cannot_adopt_issue(self):
        self.client.force_authenticate(user=self.mentor)
        resp = self.client.post(f"/api/issues/{self.issue.id}/adopt/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_h02_unassigned_coordinator_cannot_silently_adopt(self):
        self.client.force_authenticate(user=self.unassigned_coord)
        resp = self.client.post(f"/api/issues/{self.issue.id}/adopt/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("active university affiliation", resp.data.get("error", ""))

    def test_h02_valid_coordinator_can_adopt(self):
        self.client.force_authenticate(user=self.coord)
        resp = self.client.post(f"/api/issues/{self.issue.id}/adopt/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.ADOPTED)

    def test_h02_mentor_cannot_moderate_issue(self):
        self.client.force_authenticate(user=self.mentor)
        resp = self.client.post(f"/api/issues/{self.issue.id}/moderate/", {"action": "approve"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------
    # H-03 Tests: Project Privacy & Scoped Access
    # -------------------------------------------------------------
    def test_h03_unauthenticated_cannot_access_project_endpoints(self):
        # Status history
        resp1 = self.client.get(f"/api/pitches/projects/{self.project.id}/status-history/")
        self.assertEqual(resp1.status_code, status.HTTP_401_UNAUTHORIZED)

        # Discussions
        resp2 = self.client.get(f"/api/pitches/projects/{self.project.id}/discussions/")
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)

        # Engagements
        resp3 = self.client.get(f"/api/pitches/projects/{self.project.id}/engagements/")
        self.assertEqual(resp3.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_h03_unrelated_student_denied_access(self):
        self.client.force_authenticate(user=self.student_unrelated)
        resp1 = self.client.get(f"/api/pitches/projects/{self.project.id}/status-history/")
        self.assertEqual(resp1.status_code, status.HTTP_403_FORBIDDEN)

        resp2 = self.client.get(f"/api/pitches/projects/{self.project.id}/discussions/")
        self.assertEqual(resp2.status_code, status.HTTP_403_FORBIDDEN)

        resp3 = self.client.post(f"/api/pitches/projects/{self.project.id}/discussions/", {"content": "Sneak comment"})
        self.assertEqual(resp3.status_code, status.HTTP_403_FORBIDDEN)

        resp4 = self.client.get(f"/api/pitches/projects/{self.project.id}/engagements/")
        self.assertEqual(resp4.status_code, status.HTTP_403_FORBIDDEN)

    def test_h03_project_team_member_has_access(self):
        self.client.force_authenticate(user=self.student_team_lead)
        resp1 = self.client.get(f"/api/pitches/projects/{self.project.id}/status-history/")
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        resp2 = self.client.get(f"/api/pitches/projects/{self.project.id}/discussions/")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

        resp3 = self.client.post(f"/api/pitches/projects/{self.project.id}/discussions/", {"content": "Initial team meeting scheduled."})
        self.assertEqual(resp3.status_code, status.HTTP_201_CREATED)

    # -------------------------------------------------------------
    # H-04 Tests: Engagement State Machine Integrity
    # -------------------------------------------------------------
    def test_h04_engagement_state_machine(self):
        # Create engagement in REQUESTED state (proposed by industry)
        engagement = IndustryEngagement.objects.create(
            issue=self.issue,
            project=self.project,
            pitch=self.pitch,
            industry_org=self.org,
            created_by=self.industry_user,
            initiator=IndustryEngagement.Initiator.INDUSTRY,
            engagement_type=IndustryEngagement.EngagementType.MENTORSHIP,
            status=IndustryEngagement.Status.REQUESTED
        )

        # Coordinator adopts issue first to have adoption relation
        Adoption.objects.create(issue=self.issue, university=self.univ, coordinator=self.coord)

        self.client.force_authenticate(user=self.coord)

        # Invalid transition: cannot complete from REQUESTED
        resp_bad = self.client.post(f"/api/engagements/{engagement.id}/respond/", {"action": "complete"})
        self.assertEqual(resp_bad.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid transition: accept
        resp_accept = self.client.post(f"/api/engagements/{engagement.id}/respond/", {"action": "accept"})
        self.assertEqual(resp_accept.status_code, status.HTTP_200_OK)
        engagement.refresh_from_db()
        self.assertEqual(engagement.status, IndustryEngagement.Status.ACCEPTED)

        # Valid transition: activate
        resp_act = self.client.post(f"/api/engagements/{engagement.id}/respond/", {"action": "activate"})
        self.assertEqual(resp_act.status_code, status.HTTP_200_OK)
        engagement.refresh_from_db()
        self.assertEqual(engagement.status, IndustryEngagement.Status.ACTIVE)

        # Valid transition: complete
        resp_comp = self.client.post(f"/api/engagements/{engagement.id}/respond/", {"action": "complete"})
        self.assertEqual(resp_comp.status_code, status.HTTP_200_OK)
        engagement.refresh_from_db()
        self.assertEqual(engagement.status, IndustryEngagement.Status.COMPLETED)

        # Terminal state: cannot modify further
        resp_terminal = self.client.post(f"/api/engagements/{engagement.id}/respond/", {"action": "activate"})
        self.assertEqual(resp_terminal.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("terminal state", resp_terminal.data.get("error", ""))

        # Verify activity was logged
        events = ActivityEvent.objects.filter(object_id=str(engagement.id))
        self.assertTrue(events.exists())

    # -------------------------------------------------------------
    # H-06 Tests: User Certificate Listing
    # -------------------------------------------------------------
    def test_h06_user_certificate_listing(self):
        # Create authentic certificate for student_team_lead
        cert = Certificate.objects.create(
            certificate_id="CONF-2026-TEST01",
            recipient=self.student_team_lead,
            project=self.project,
            challenge=self.issue,
            solution=self.pitch,
            role=Certificate.Role.STUDENT_INNOVATOR,
            title="Certificate of Verified Civic Innovation",
            verification_hash="abc1234567890abcdef1234567890abcdef1234567890abcdef1234567890abc"
        )

        # Unauthenticated: 401
        resp_unauth = self.client.get("/api/pitches/certificates/")
        self.assertEqual(resp_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticated student can see their certificate
        self.client.force_authenticate(user=self.student_team_lead)
        resp_auth = self.client.get("/api/pitches/certificates/")
        self.assertEqual(resp_auth.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_auth.data), 1)
        self.assertEqual(resp_auth.data[0]["certificate_id"], "CONF-2026-TEST01")

        # certificates/mine/ route also works
        resp_mine = self.client.get("/api/pitches/certificates/mine/")
        self.assertEqual(resp_mine.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_mine.data), 1)

        # Another user cannot see this certificate
        self.client.force_authenticate(user=self.student_unrelated)
        resp_other = self.client.get("/api/pitches/certificates/")
        self.assertEqual(resp_other.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_other.data), 0)

    # -------------------------------------------------------------
    # H-07 Tests: Settings Hardening
    # -------------------------------------------------------------
    def test_h07_settings_hardening(self):
        self.assertEqual(settings.SIMPLE_JWT.get("SIGNING_KEY"), settings.SECRET_KEY)
        self.assertTrue(settings.CORS_ALLOW_CREDENTIALS)
        self.assertFalse(settings.CORS_ALLOW_ALL_ORIGINS)
        self.assertIsInstance(settings.CORS_ALLOWED_ORIGINS, list)
        self.assertIn("http://localhost:5173", settings.CORS_ALLOWED_ORIGINS)
