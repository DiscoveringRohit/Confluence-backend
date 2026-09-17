from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.users.models import User, University, Organization
from apps.issues.models import Issue, Adoption
from apps.pitches.models import Pitch, Project, ProjectMilestone, Certificate


class CriticalFixesTestCase(TestCase):
    """
    Regression test suite for Critical findings from the security & workflow audit:
    - C-01: Privileged account self-registration restrictions
    - C-02: Project API object-level authorization & field immutability
    - C-04: Deployment evidence persistence, state transition gates, and certificate eligibility
    """

    def setUp(self):
        self.client = APIClient()

        # Universities
        self.uni_a = University.objects.create(name="IIT ISM Dhanbad", district="Dhanbad")
        self.uni_b = University.objects.create(name="Ranchi University", district="Ranchi")

        # Organizations
        self.org = Organization.objects.create(name="Tata Power CSR", org_type="csr")

        # Users for Uni A
        self.coord_a = User.objects.create_user(
            email="coord_a@ism.ac.in",
            name="ISM Coordinator",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_a
        )
        self.mentor_a = User.objects.create_user(
            email="mentor_a@ism.ac.in",
            name="Prof. Sen (Mentor)",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni_a
        )
        self.student_team = User.objects.create_user(
            email="student_team@ism.ac.in",
            name="Student Team Member",
            role=User.Role.STUDENT,
            university=self.uni_a
        )

        # Users for Uni B / External
        self.coord_b = User.objects.create_user(
            email="coord_b@ru.ac.in",
            name="RU Coordinator",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_b
        )
        self.student_other = User.objects.create_user(
            email="student_other@ru.ac.in",
            name="Other Student",
            role=User.Role.STUDENT,
            university=self.uni_b
        )

        # Citizens
        self.citizen_owner = User.objects.create_user(
            email="citizen_owner@jharkhand.in",
            name="Citizen Reporter",
            role=User.Role.CITIZEN
        )
        self.citizen_unrelated = User.objects.create_user(
            email="citizen_unrelated@jharkhand.in",
            name="Unrelated Citizen",
            role=User.Role.CITIZEN
        )

        # Issue & Adoption
        self.issue = Issue.objects.create(
            title="Solar Microgrid Failure in Tundi Village",
            description="Battery bank degraded and inverter trips daily.",
            category="electricity",
            district="Dhanbad",
            submitted_by=self.citizen_owner,
            status=Issue.Status.ADOPTED
        )
        self.adoption = Adoption.objects.create(
            issue=self.issue,
            university=self.uni_a,
            coordinator=self.coord_a
        )

        # Pitch & Project
        self.pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.uni_a,
            title="Smart Lithium-Iron Microgrid Controller",
            public_summary="IoT battery balancer and remote cloud telemetry.",
            status=Pitch.Status.SELECTED,
            assigned_mentor=self.mentor_a
        )
        self.pitch.student_team.add(self.student_team)

        self.project = Project.objects.create(
            solution=self.pitch,
            challenge=self.issue,
            university=self.uni_a,
            mentor=self.mentor_a,
            title="Tundi Microgrid Implementation Project",
            status=Project.Status.PILOT
        )
        self.project.team.add(self.student_team)

    # -------------------------------------------------------------------------
    # C-01: Registration Tests
    # -------------------------------------------------------------------------
    def test_c01_cannot_register_privileged_roles(self):
        """Privileged accounts (gov_admin, coordinator, mentor, industry) cannot self-register."""
        for role in [User.Role.GOV_ADMIN, User.Role.UNIVERSITY_COORDINATOR, User.Role.FACULTY_MENTOR, User.Role.INDUSTRY_PARTNER]:
            res = self.client.post("/api/auth/register/", {
                "email": f"malicious_{role}@example.com",
                "password": "Password123!",
                "name": "Malicious Caller",
                "role": role,
                "university": self.uni_a.id
            })
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("role", res.data)

    def test_c01_student_registration_requires_university(self):
        """Student registration requires a university affiliation."""
        res = self.client.post("/api/auth/register/", {
            "email": "student_no_uni@example.com",
            "password": "Password123!",
            "name": "Student Without Uni",
            "role": "student"
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("university", res.data)

    def test_c01_citizen_registration_succeeds_without_affiliation(self):
        """Citizen registration succeeds and sanitizes any institution associations."""
        res = self.client.post("/api/auth/register/", {
            "email": "legit_citizen@jharkhand.in",
            "password": "Password123!",
            "name": "Legit Citizen",
            "role": "citizen",
            "university": self.uni_a.id,
            "organization": self.org.id
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="legit_citizen@jharkhand.in")
        self.assertEqual(user.role, User.Role.CITIZEN)
        self.assertIsNone(user.university)
        self.assertIsNone(user.organization)

    # -------------------------------------------------------------------------
    # C-02: Project Authorization & Immutability Tests
    # -------------------------------------------------------------------------
    def test_c02_unrelated_student_cannot_access_project(self):
        """Unrelated student from another university cannot retrieve project (404/Not Found)."""
        self.client.force_authenticate(user=self.student_other)
        res = self.client.get(f"/api/pitches/projects/{self.project.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_c02_unrelated_citizen_cannot_access_project(self):
        """Citizen who did not submit the underlying issue cannot view the project."""
        self.client.force_authenticate(user=self.citizen_unrelated)
        res = self.client.get(f"/api/pitches/projects/{self.project.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_c02_external_coordinator_cannot_access_project(self):
        """Coordinator from an unrelated university cannot view or update the project."""
        self.client.force_authenticate(user=self.coord_b)
        res_get = self.client.get(f"/api/pitches/projects/{self.project.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        res_patch = self.client.patch(f"/api/pitches/projects/{self.project.id}/", {"title": "Hacked Title"})
        self.assertEqual(res_patch.status_code, status.HTTP_404_NOT_FOUND)

    def test_c02_team_student_can_read_but_cannot_patch_project(self):
        """Student team members can view project, but cannot PATCH project details (403)."""
        self.client.force_authenticate(user=self.student_team)
        res_get = self.client.get(f"/api/pitches/projects/{self.project.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)

        res_patch = self.client.patch(f"/api/pitches/projects/{self.project.id}/", {"title": "Student Updated Title"})
        self.assertEqual(res_patch.status_code, status.HTTP_403_FORBIDDEN)

    def test_c02_citizen_reporter_can_read_but_cannot_patch_project(self):
        """Citizen reporter can view project progress, but cannot PATCH project details (403)."""
        self.client.force_authenticate(user=self.citizen_owner)
        res_get = self.client.get(f"/api/pitches/projects/{self.project.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)

        res_patch = self.client.patch(f"/api/pitches/projects/{self.project.id}/", {"title": "Citizen Updated Title"})
        self.assertEqual(res_patch.status_code, status.HTTP_403_FORBIDDEN)

    def test_c02_coordinator_patch_cannot_mutate_workflow_fields(self):
        """Authorized coordinator PATCH cannot overwrite status, deployment_evidence, or university."""
        self.client.force_authenticate(user=self.coord_a)
        res_patch = self.client.patch(
            f"/api/pitches/projects/{self.project.id}/",
            {
                "title": "Legitimately Updated Project Title",
                "status": "resolved",
                "deployment_evidence": "Fabricated evidence string",
                "university": self.uni_b.id
            }
        )
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Legitimately Updated Project Title")
        self.assertEqual(self.project.status, Project.Status.PILOT)
        self.assertEqual(self.project.deployment_evidence, "")
        self.assertEqual(self.project.university_id, self.uni_a.id)

    # -------------------------------------------------------------------------
    # C-04: Deployment Evidence Persistence & Transition Integrity Tests
    # -------------------------------------------------------------------------
    def test_c04_submit_deployment_persists_evidence_and_outcome(self):
        """Submitting deployment evidence saves deployment_evidence and outcome to DB."""
        self.client.force_authenticate(user=self.student_team)
        evidence_text = "5kW smart inverter installed with cloud telemetry live at http://telemetry.tundi.in"
        outcome_text = "Stabilized 230V AC supply to 45 tribal households."

        res = self.client.post(
            f"/api/pitches/projects/{self.project.id}/submit-deployment/",
            {
                "deployment_evidence": evidence_text,
                "outcome": outcome_text
            }
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Crucial C-04 check: refresh from DB to verify persistence
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.DEPLOYMENT_READY)
        self.assertEqual(self.project.deployment_evidence, evidence_text)
        self.assertEqual(self.project.outcome, outcome_text)

    def test_c04_approve_deployment_enforces_deployment_ready_state(self):
        """Approving deployment before submitting evidence (while in PILOT) is rejected."""
        self.client.force_authenticate(user=self.mentor_a)
        res = self.client.post(f"/api/pitches/projects/{self.project.id}/approve-deployment/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Deployment Ready", res.data["error"])

    def test_c04_end_to_end_deployment_verification_and_certificates(self):
        """
        Complete flow:
        1. Submit deployment -> evidence persisted in DB.
        2. Mentor approves deployment -> DEPLOYED -> AWAITING_CITIZEN_VERIFICATION.
        3. Citizen confirms resolution -> Project VERIFIED.
        4. Generate certificate -> succeeds because deployment_evidence was preserved!
        """
        # 1. Submit deployment
        self.client.force_authenticate(user=self.student_team)
        evidence_text = "Full commissioning report signed by Panchayat Pradhan and testing logs attached."
        res_submit = self.client.post(
            f"/api/pitches/projects/{self.project.id}/submit-deployment/",
            {
                "deployment_evidence": evidence_text,
                "outcome": "45 households powered."
            }
        )
        self.assertEqual(res_submit.status_code, status.HTTP_200_OK)

        # 2. Mentor approves deployment
        self.client.force_authenticate(user=self.mentor_a)
        res_approve = self.client.post(f"/api/pitches/projects/{self.project.id}/approve-deployment/")
        self.assertEqual(res_approve.status_code, status.HTTP_200_OK)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.AWAITING_CITIZEN_VERIFICATION)
        self.assertEqual(self.project.deployment_status, "deployed")
        self.assertEqual(self.project.deployment_evidence, evidence_text)

        # 3. Citizen confirms resolution
        self.client.force_authenticate(user=self.citizen_owner)
        res_citizen = self.client.post(
            f"/api/issues/{self.issue.id}/citizen-confirm-resolution/",
            {"confirmed": True, "feedback": "Solar power is now reliable. Thank you!"}
        )
        self.assertEqual(res_citizen.status_code, status.HTTP_200_OK)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.VERIFIED)

        # 4. Coordinator triggers certificate generation
        self.client.force_authenticate(user=self.coord_a)
        res_cert = self.client.post(f"/api/pitches/projects/{self.project.id}/certificates/generate/")
        self.assertIn(res_cert.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

        # Verify certificate was issued for the student team member and mentor
        student_cert = Certificate.objects.filter(project=self.project, recipient=self.student_team).first()
        self.assertIsNotNone(student_cert)
        self.assertEqual(student_cert.role, Certificate.Role.STUDENT_INNOVATOR)

        mentor_cert = Certificate.objects.filter(project=self.project, recipient=self.mentor_a).first()
        self.assertIsNotNone(mentor_cert)
        self.assertEqual(mentor_cert.role, Certificate.Role.FACULTY_MENTOR)
