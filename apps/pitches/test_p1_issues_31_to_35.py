from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from apps.users.models import User, University
from apps.issues.models import Issue, Adoption
from apps.pitches.models import (
    Pitch, SolutionTeamMember, ReviewSession, Project, ProjectMilestone
)


class P1Issues31To35TestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Universities
        self.uni_a = University.objects.create(name="BIT Sindri", district="Dhanbad")
        self.uni_b = University.objects.create(name="Ranchi University", district="Ranchi")

        # Users
        self.citizen = User.objects.create_user(
            email="citizen_31@jharkhand.in",
            name="Citizen Reporter",
            role=User.Role.CITIZEN
        )
        self.coord_a = User.objects.create_user(
            email="coord_31@bitsindri.ac.in",
            name="Coordinator BIT",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_a
        )
        self.coord_b = User.objects.create_user(
            email="coord_31@ranchi.ac.in",
            name="Coordinator RU",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_b
        )
        self.mentor_a = User.objects.create_user(
            email="mentor_prof_31@bitsindri.ac.in",
            name="Prof. Sharma (BIT Mentor)",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni_a
        )
        self.mentor_b = User.objects.create_user(
            email="mentor_prof_31@ranchi.ac.in",
            name="Prof. Verma (RU Mentor)",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni_b
        )
        self.student_lead = User.objects.create_user(
            email="student_lead_31@bitsindri.ac.in",
            name="Student Leader",
            role=User.Role.STUDENT,
            university=self.uni_a
        )
        self.student_other = User.objects.create_user(
            email="student_other_31@ranchi.ac.in",
            name="Other Student",
            role=User.Role.STUDENT,
            university=self.uni_b
        )

        # Issue and Adoption
        self.issue = Issue.objects.create(
            title="Clean Drinking Water Solar ATM for Topchanchi",
            description="Contaminated ground water in remote habitations.",
            category="water",
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
            title="Solar-Powered IoT Reverse Osmosis Water ATM",
            public_summary="Solar-powered decentralized clean water kiosk with RFID tokens.",
            confidential_package="Low-maintenance membranes, telemetry battery management, automated backwash cycle.",
            repository_url="https://github.com/bitsindri/solar-water-atm",
            status=Pitch.Status.SUBMITTED,
            assigned_mentor=self.mentor_a
        )
        self.pitch.student_team.add(self.student_lead)
        SolutionTeamMember.objects.create(
            pitch=self.pitch,
            student=self.student_lead,
            role=SolutionTeamMember.Role.OWNER
        )

    # -------------------------------------------------------------
    # Issue 31: Review Session Model & Endpoints
    # -------------------------------------------------------------
    def test_review_session_persistence_and_authorization(self):
        """Coordinators can schedule review sessions; persisted with date, panelists, and agenda."""
        self.client.force_authenticate(user=self.coord_a)
        payload = {
            "title": "Quarterly Innovation Board Evaluation",
            "scheduled_at": "2026-10-15T14:30:00Z",
            "panelists": "Prof. S. Soren, Dr. P. Mishra, Tech Lead (JUSCO)",
            "notes": "Evaluate IoT water ATM prototype and biochar sand filter.",
            "challenge": self.issue.id,
            "pitch": self.pitch.id,
        }
        res = self.client.post("/api/pitches/review-sessions/", payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        session_id = res.data["id"]
        self.assertEqual(res.data["title"], "Quarterly Innovation Board Evaluation")
        self.assertEqual(res.data["status"], "scheduled")

        # Verify query list
        res_list = self.client.get("/api/pitches/review-sessions/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        results = res_list.data if isinstance(res_list.data, list) else res_list.data.get("results", [])
        self.assertTrue(any(s["id"] == session_id for s in results))

    def test_student_cannot_create_review_session(self):
        """Students cannot schedule review sessions (403 Forbidden)."""
        self.client.force_authenticate(user=self.student_lead)
        payload = {
            "title": "Unauthorized Session",
            "scheduled_at": "2026-10-15T14:30:00Z",
            "panelists": "Self",
        }
        res = self.client.post("/api/pitches/review-sessions/", payload)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------
    # Issue 32 & 33: Project Model & Canonical States
    # -------------------------------------------------------------
    def test_project_auto_creation_on_winner_selection(self):
        """Selecting winning pitch automatically instantiates real Project with initial milestones."""
        self.client.force_authenticate(user=self.coord_a)
        res = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {"action": "select_winner", "review_feedback": "Selected for university incubation."}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Verify Project created
        project = Project.objects.get(solution=self.pitch)
        self.assertEqual(project.challenge, self.issue)
        self.assertEqual(project.university, self.uni_a)
        self.assertEqual(project.mentor, self.mentor_a)
        self.assertEqual(project.status, Project.Status.PLANNING)
        self.assertTrue(project.team.filter(id=self.student_lead.id).exists())

        # Verify 4 default milestones instantiated
        self.assertEqual(project.milestones.count(), 4)
        m1 = project.milestones.first()
        self.assertEqual(m1.order, 1)
        self.assertEqual(m1.status, ProjectMilestone.Status.PENDING)

    def test_project_state_transitions(self):
        """Project transitions through canonical states with audit logging."""
        project = Project.objects.create(
            solution=self.pitch,
            challenge=self.issue,
            university=self.uni_a,
            mentor=self.mentor_a,
            title="Solar Water ATM Project",
            status=Project.Status.PLANNING
        )
        project.team.add(self.student_lead)

        # Transition PLANNING -> PROTOTYPE
        project.transition_status(Project.Status.PROTOTYPE, actor=self.coord_a, reason="Design freeze completed")
        project.refresh_from_db()
        self.assertEqual(project.status, Project.Status.PROTOTYPE)

    # -------------------------------------------------------------
    # Issue 34: ProjectMilestone Evidence & Review Workflow
    # -------------------------------------------------------------
    def test_milestone_evidence_submission_by_student(self):
        """Student team member submits evidence; status transitions to SUBMITTED."""
        project = Project.objects.create(
            solution=self.pitch,
            challenge=self.issue,
            university=self.uni_a,
            mentor=self.mentor_a,
            title="Solar Water ATM Project",
            status=Project.Status.PROTOTYPE
        )
        project.team.add(self.student_lead)

        milestone = ProjectMilestone.objects.create(
            project=project,
            order=1,
            title="Fabricate Solar Inverter Subsystem",
            status=ProjectMilestone.Status.IN_PROGRESS
        )

        self.client.force_authenticate(user=self.student_lead)
        patch_res = self.client.patch(
            f"/api/pitches/projects/{project.id}/milestones/{milestone.id}/",
            {"evidence": "https://github.com/bitsindri/solar-water-atm/commit/abc1234 Lab validation test passed."}
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        milestone.refresh_from_db()
        self.assertEqual(milestone.status, ProjectMilestone.Status.SUBMITTED)
        self.assertIsNotNone(milestone.submitted_at)

    def test_non_team_student_cannot_modify_milestone(self):
        """Students from other universities/teams cannot modify milestones (403)."""
        project = Project.objects.create(
            solution=self.pitch,
            challenge=self.issue,
            university=self.uni_a,
            mentor=self.mentor_a,
            title="Solar Water ATM Project",
            status=Project.Status.PROTOTYPE
        )
        milestone = ProjectMilestone.objects.create(
            project=project,
            order=1,
            title="Test Milestone"
        )

        self.client.force_authenticate(user=self.student_other)
        patch_res = self.client.patch(
            f"/api/pitches/projects/{project.id}/milestones/{milestone.id}/",
            {"evidence": "Malicious tampering"}
        )
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_mentor_can_approve_or_request_changes_on_milestone(self):
        """Assigned faculty mentor reviews milestone: requests changes or approves."""
        project = Project.objects.create(
            solution=self.pitch,
            challenge=self.issue,
            university=self.uni_a,
            mentor=self.mentor_a,
            title="Solar Water ATM Project",
            status=Project.Status.PROTOTYPE
        )
        milestone = ProjectMilestone.objects.create(
            project=project,
            order=1,
            title="Battery Enclosure Weatherproofing",
            status=ProjectMilestone.Status.SUBMITTED,
            evidence="Enclosure IP65 silicone gasket seal installed."
        )

        # 1. Mentor requests changes
        self.client.force_authenticate(user=self.mentor_a)
        res_changes = self.client.post(
            f"/api/pitches/projects/{project.id}/milestones/{milestone.id}/review/",
            {"action": "request_changes", "feedback": "Provide temperature heat-dissipation test data."}
        )
        self.assertEqual(res_changes.status_code, status.HTTP_200_OK)
        milestone.refresh_from_db()
        self.assertEqual(milestone.status, ProjectMilestone.Status.CHANGES_REQUESTED)
        self.assertEqual(milestone.reviewer, self.mentor_a)

        # 2. Mentor approves after revision
        res_approve = self.client.post(
            f"/api/pitches/projects/{project.id}/milestones/{milestone.id}/review/",
            {"action": "approve", "feedback": "Thermal telemetry within normal range. Approved."}
        )
        self.assertEqual(res_approve.status_code, status.HTTP_200_OK)
        milestone.refresh_from_db()
        self.assertEqual(milestone.status, ProjectMilestone.Status.APPROVED)

    # -------------------------------------------------------------
    # Issue 35: Deployment Gate Workflow
    # -------------------------------------------------------------
    def test_submit_deployment_requires_evidence(self):
        """Submitting deployment without evidence is rejected with 400 Bad Request."""
        project = Project.objects.create(
            solution=self.pitch,
            challenge=self.issue,
            university=self.uni_a,
            mentor=self.mentor_a,
            title="Solar Water ATM Project",
            status=Project.Status.PILOT
        )
        project.team.add(self.student_lead)

        self.client.force_authenticate(user=self.student_lead)
        res_empty = self.client.post(
            f"/api/pitches/projects/{project.id}/submit-deployment/",
            {"deployment_evidence": ""}
        )
        self.assertEqual(res_empty.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid submission
        res_valid = self.client.post(
            f"/api/pitches/projects/{project.id}/submit-deployment/",
            {
                "deployment_evidence": "Installed at Topchanchi Community Health Center with 24h IoT flow monitoring.",
                "outcome": "Supplying 2,000L/day potable water."
            }
        )
        self.assertEqual(res_valid.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.status, Project.Status.DEPLOYMENT_READY)

    def test_approve_deployment_gate_workflow(self):
        """
        Approving deployment transitions project to DEPLOYED -> AWAITING_CITIZEN_VERIFICATION,
        and transitions challenge to AWAITING_VERIFICATION (NOT directly RESOLVED).
        """
        project = Project.objects.create(
            solution=self.pitch,
            challenge=self.issue,
            university=self.uni_a,
            mentor=self.mentor_a,
            title="Solar Water ATM Project",
            status=Project.Status.DEPLOYMENT_READY,
            deployment_evidence="Pre-commissioning checklist signed by panchayat head and faculty mentor."
        )

        # Student cannot approve deployment
        self.client.force_authenticate(user=self.student_lead)
        res_unauthorized = self.client.post(f"/api/pitches/projects/{project.id}/approve-deployment/")
        self.assertEqual(res_unauthorized.status_code, status.HTTP_403_FORBIDDEN)

        # Mentor approves deployment
        self.client.force_authenticate(user=self.mentor_a)
        res_approve = self.client.post(f"/api/pitches/projects/{project.id}/approve-deployment/")
        self.assertEqual(res_approve.status_code, status.HTTP_200_OK)

        project.refresh_from_db()
        self.issue.refresh_from_db()
        self.assertEqual(project.status, Project.Status.AWAITING_CITIZEN_VERIFICATION)
        self.assertEqual(self.issue.status, Issue.Status.AWAITING_VERIFICATION)
        self.assertNotEqual(self.issue.status, Issue.Status.RESOLVED)

    def test_citizen_verification_updates_project_and_issue_status(self):
        """
        Citizen verification gate:
        - Confirm resolution -> Issue RESOLVED, Project VERIFIED.
        - Reject resolution -> Issue REOPENED, Project REOPENED.
        """
        project = Project.objects.create(
            solution=self.pitch,
            challenge=self.issue,
            university=self.uni_a,
            mentor=self.mentor_a,
            title="Solar Water ATM Project",
            status=Project.Status.AWAITING_CITIZEN_VERIFICATION,
            deployment_evidence="Live water ATM"
        )
        self.issue.status = Issue.Status.AWAITING_VERIFICATION
        self.issue.save()

        # 1. Citizen confirms resolution
        self.client.force_authenticate(user=self.citizen)
        res_confirm = self.client.post(
            f"/api/issues/{self.issue.id}/citizen-confirm-resolution/",
            {"confirmed": True, "feedback": "Water ATM working reliably with good TDS."}
        )
        self.assertEqual(res_confirm.status_code, status.HTTP_200_OK)

        project.refresh_from_db()
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.RESOLVED)
        self.assertEqual(project.status, Project.Status.VERIFIED)

        # 2. Rejection workflow test
        project.status = Project.Status.AWAITING_CITIZEN_VERIFICATION
        project.save()
        self.issue.status = Issue.Status.AWAITING_VERIFICATION
        self.issue.save()

        res_reject = self.client.post(
            f"/api/issues/{self.issue.id}/citizen-confirm-resolution/",
            {"confirmed": False, "feedback": "Solar inverter tripped during rain, pump stopped working."}
        )
        self.assertEqual(res_reject.status_code, status.HTTP_200_OK)

        project.refresh_from_db()
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.REOPENED)
        self.assertEqual(project.status, Project.Status.REOPENED)
