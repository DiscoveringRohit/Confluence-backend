from django.test import TestCase
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from apps.users.models import User, University, Organization
from apps.issues.models import Issue
from apps.pitches.models import Pitch, Project

class MediumFixesTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.uni_a = University.objects.create(name="IIT ISM Dhanbad", district="Dhanbad", code="IITISM")
        self.uni_b = University.objects.create(name="BIT Mesra", district="Ranchi", code="BITM")

        # Users
        self.staff_admin = User.objects.create_user(
            email="admin@jharkhand.gov.in",
            password="Password123",
            name="State Admin",
            role=User.Role.GOV_ADMIN,
            is_staff=True
        )
        self.student_a1 = User.objects.create_user(
            email="student1@iitism.ac.in",
            password="Password123",
            name="Student A1",
            role=User.Role.STUDENT,
            university=self.uni_a,
            phone="9876543210"
        )
        self.student_a2 = User.objects.create_user(
            email="student2@iitism.ac.in",
            password="Password123",
            name="Student A2",
            role=User.Role.STUDENT,
            university=self.uni_a,
            phone="9876543211"
        )
        self.student_b = User.objects.create_user(
            email="student_b@bitmesra.ac.in",
            password="Password123",
            name="Student B",
            role=User.Role.STUDENT,
            university=self.uni_b,
            phone="9876543212"
        )
        self.citizen = User.objects.create_user(
            email="citizen@jharkhand.in",
            password="Password123",
            name="Citizen User",
            role=User.Role.CITIZEN
        )
        self.coord_a = User.objects.create_user(
            email="coord@iitism.ac.in",
            password="Password123",
            name="Coordinator A",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_a
        )
        self.mentor_a = User.objects.create_user(
            email="mentor@iitism.ac.in",
            password="Password123",
            name="Mentor A",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni_a
        )

    # --- M-01 & M-06 Tests ---
    def test_m01_user_directory_permission_and_pii_sanitization(self):
        # 1. Citizen cannot view global /api/users/ directory
        self.client.force_authenticate(user=self.citizen)
        res = self.client.get("/api/users/")
        self.assertEqual(res.status_code, 403)

        # 2. Staff can view global directory
        self.client.force_authenticate(user=self.staff_admin)
        res = self.client.get("/api/users/")
        self.assertEqual(res.status_code, 200)

        # 3. Student A1 can view students in Uni A
        self.client.force_authenticate(user=self.student_a1)
        res = self.client.get(f"/api/users/universities/{self.uni_a.id}/students/")
        self.assertEqual(res.status_code, 200)
        results = res.data if isinstance(res.data, list) else res.data.get('results', [])
        self.assertTrue(len(results) >= 2)
        # Ensure phone PII is NOT present in directory serializer
        for stud in results:
            self.assertNotIn("phone", stud)

        # 4. Student A1 cannot view students in Uni B
        res = self.client.get(f"/api/users/universities/{self.uni_b.id}/students/")
        self.assertEqual(res.status_code, 403)

    def test_m06_user_detail_endpoint(self):
        # User viewing own details
        self.client.force_authenticate(user=self.student_a1)
        res = self.client.get(f"/api/users/{self.student_a1.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['email'], self.student_a1.email)

        # Student A1 cannot view citizen details
        res = self.client.get(f"/api/users/{self.citizen.id}/")
        self.assertEqual(res.status_code, 403)

        # Coordinator A can view affiliated Student A1 details
        self.client.force_authenticate(user=self.coord_a)
        res = self.client.get(f"/api/users/{self.student_a1.id}/")
        self.assertEqual(res.status_code, 200)
        # But Coordinator A cannot view Student B details
        res = self.client.get(f"/api/users/{self.student_b.id}/")
        self.assertEqual(res.status_code, 403)

    # --- M-02 Tests ---
    def test_m02_analytics_public_vs_institutional_segmentation(self):
        # Public aggregate analytics accessible without authentication
        self.client.force_authenticate(user=None)
        res = self.client.get("/api/analytics/gov/summary/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get('is_public'))
        self.assertIn('overview', res.data)
        self.assertIn('total_issues_reported', res.data['overview'])
        self.assertEqual(len(res.data['institutional_track_record']['universities']), 0)

        # Institutional analytics blocked for unauthenticated
        res = self.client.get("/api/analytics/gov/institutional/")
        self.assertEqual(res.status_code, 401)

        # Institutional analytics accessible for staff
        self.client.force_authenticate(user=self.staff_admin)
        res = self.client.get("/api/analytics/gov/institutional/")
        self.assertEqual(res.status_code, 200)
        self.assertIn('institutional_track_record', res.data)
        self.assertIn('universities', res.data['institutional_track_record'])

    # --- M-05 Tests ---
    def test_m05_issue_state_machine_validation(self):
        issue = Issue.objects.create(
            title="Pothole Issue",
            description="Fix pothole on main road",
            category=Issue.Category.URBAN_INFRA,
            district="Dhanbad",
            status=Issue.Status.SUBMITTED,
            submitted_by=self.citizen
        )

        # Invalid transition: SUBMITTED directly to RESOLVED must raise ValidationError
        with self.assertRaises(ValidationError):
            issue.transition_status(Issue.Status.RESOLVED, actor=self.staff_admin)

        # Valid transition: SUBMITTED -> VALIDATED
        issue.transition_status(Issue.Status.VALIDATED, actor=self.staff_admin)
        self.assertEqual(issue.status, Issue.Status.VALIDATED)

        # Terminal state: RESOLVED issue cannot transition to VALIDATED
        issue.status = Issue.Status.RESOLVED
        issue.save()
        with self.assertRaises(ValidationError):
            issue.transition_status(Issue.Status.VALIDATED, actor=self.staff_admin)

    def test_m05_project_deployment_source_state_enforcement(self):
        issue = Issue.objects.create(
            title="Bridge sensor problem",
            description="Need smart IoT sensors for bridge monitoring",
            category=Issue.Category.URBAN_INFRA,
            district="Dhanbad",
            status=Issue.Status.ADOPTED,
            submitted_by=self.citizen
        )
        pitch = Pitch.objects.create(
            issue=issue,
            university=self.uni_a,
            title="IoT Bridge Monitor",
            public_summary="Smart sensors for bridge load",
            confidential_package="Proprietary strain gauge circuit"
        )
        pitch.student_team.add(self.student_a1)
        project = Project.objects.create(
            solution=pitch,
            challenge=issue,
            university=self.uni_a,
            mentor=self.mentor_a,
            status=Project.Status.CREATED
        )
        project.team.add(self.student_a1)

        # 1. Submit deployment from CREATED state must fail (only PILOT or PROTOTYPE allowed)
        self.client.force_authenticate(user=self.student_a1)
        res = self.client.post(f"/api/pitches/projects/{project.id}/submit-deployment/", {
            "deployment_evidence": "Here is our full test telemetry."
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("Deployment evidence can only be submitted from Prototype or Pilot status", res.data['error'])

        # 2. Advance project to PILOT, then submit deployment package
        project.status = Project.Status.PILOT
        project.save()

        res = self.client.post(f"/api/pitches/projects/{project.id}/submit-deployment/", {
            "deployment_evidence": "https://drive.google.com/test-telemetry-report"
        })
        self.assertEqual(res.status_code, 200)
        project.refresh_from_db()
        self.assertEqual(project.status, Project.Status.DEPLOYMENT_READY)

        # 3. Coordinator approves deployment -> atomic transition to DEPLOYED and issue to AWAITING_VERIFICATION
        self.client.force_authenticate(user=self.coord_a)
        approve_res = self.client.post(f"/api/pitches/projects/{project.id}/approve-deployment/")
        self.assertEqual(approve_res.status_code, 200)

        project.refresh_from_db()
        issue.refresh_from_db()
        self.assertEqual(project.status, Project.Status.AWAITING_CITIZEN_VERIFICATION)
        self.assertEqual(issue.status, Issue.Status.AWAITING_VERIFICATION)
