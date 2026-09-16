import json
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.users.models import User, University
from apps.issues.models import Issue, Adoption, ActivityEvent, CitizenVerification, DiscussionComment, IssueStatusHistory
from apps.pitches.models import Pitch, Project, ProjectMilestone
from apps.notifications.models import Notification

class Issues36To40TestCase(TestCase):
    """
    Test suite for P1 Issues 36 to 40 from Workflow Gap Analysis:
    - Issue 36: Citizen Verification gate
    - Issue 37: Failed Citizen Verification handling & notifications
    - Issue 38: Activity Timeline generic event querying & filtering
    - Issue 39: Status History audit endpoints
    - Issue 40: Tri-part Discussion System (Challenge, Solution, Project)
    """

    def setUp(self):
        self.client = APIClient()

        # Universities
        self.uni = University.objects.create(name="Birla Institute of Technology", district="Ranchi")
        self.other_uni = University.objects.create(name="IIT ISM Dhanbad", district="Dhanbad")

        # Users
        self.citizen = User.objects.create_user(
            email="citizen@jharkhand.in",
            password="Password@123",
            name="Rameshwar Citizen",
            role="citizen"
        )
        self.other_citizen = User.objects.create_user(
            email="other_citizen@jharkhand.in",
            password="Password@123",
            name="Other Citizen",
            role="citizen"
        )
        self.coordinator = User.objects.create_user(
            email="coord@bit.edu",
            password="Password@123",
            name="Prof Coordinator",
            role="university_coordinator",
            university=self.uni
        )
        self.mentor = User.objects.create_user(
            email="mentor@bit.edu",
            password="Password@123",
            name="Dr Mentor",
            role="faculty_mentor",
            university=self.uni
        )
        self.student = User.objects.create_user(
            email="student@bit.edu",
            password="Password@123",
            name="Priya Student",
            role="student",
            university=self.uni
        )

        # Challenge / Issue
        self.issue = Issue.objects.create(
            title="Contaminated Borewell in Angara",
            description="High arsenic and fluoride levels affecting 400 households.",
            district="Ranchi",
            submitted_by=self.citizen,
            status=Issue.Status.AWAITING_VERIFICATION,
            photo_url="https://example.com/water.jpg"
        )
        self.adoption = Adoption.objects.create(
            issue=self.issue,
            university=self.uni,
            coordinator=self.coordinator,
            status=Adoption.Status.APPROVED
        )

        # Pitch & Project
        self.pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.uni,
            title="Solar-Powered Multistage Fluoride Filter",
            public_summary="Community filtration plant.",
            assigned_mentor=self.mentor,
            status=Pitch.Status.SELECTED
        )
        self.pitch.student_team.add(self.student)

        self.project = Project.objects.create(
            solution=self.pitch,
            challenge=self.issue,
            university=self.uni,
            mentor=self.mentor,
            title=self.pitch.title,
            status=Project.Status.DEPLOYMENT_READY,
            deployment_status="deployed",
            deployment_evidence="Telemetry logs: https://example.com/telemetry"
        )
        self.project.team.add(self.student)

    # -------------------------------------------------------------
    # Issue 36: Citizen Verification Gate
    # -------------------------------------------------------------
    def test_citizen_verification_requires_deployed_or_awaiting_stage(self):
        """Pre-implementation challenge stages (e.g. SUBMITTED, ADOPTED) cannot be verified."""
        early_issue = Issue.objects.create(
            title="Unadopted Pothole Issue",
            description="Potholes on highway.",
            district="Ranchi",
            submitted_by=self.citizen,
            status=Issue.Status.SUBMITTED,
            photo_url="https://example.com/pothole.jpg"
        )
        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f"/api/issues/{early_issue.id}/confirm-resolution/", {
            "confirmed": True,
            "feedback": "All good."
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("must be deployed or awaiting verification", res.data.get('error', ''))

    def test_citizen_verification_restricted_to_submitting_citizen(self):
        """Only the original citizen submitter (or admin) can confirm resolution."""
        self.client.force_authenticate(user=self.other_citizen)
        res = self.client.post(f"/api/issues/{self.issue.id}/confirm-resolution/", {
            "confirmed": True,
            "feedback": "I live nearby and it seems fine."
        })
        self.assertEqual(res.status_code, 403)

    def test_successful_citizen_verification_resolves_challenge_and_verifies_project(self):
        """Citizen confirms resolution -> challenge becomes RESOLVED, project becomes VERIFIED."""
        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f"/api/issues/{self.issue.id}/confirm-resolution/", {
            "confirmed": True,
            "feedback": "Water quality tested clear. Community is drinking safely now!"
        })
        self.assertEqual(res.status_code, 200)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.RESOLVED)
        self.assertTrue(self.issue.citizen_verified_resolved)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.VERIFIED)

        # Verification audit record
        verif = CitizenVerification.objects.filter(issue=self.issue).first()
        self.assertIsNotNone(verif)
        self.assertEqual(verif.result, CitizenVerification.Result.VERIFIED)

        # Activity logged
        self.assertTrue(ActivityEvent.objects.filter(
            issue=self.issue,
            event_type='citizen_verification'
        ).exists())

    # -------------------------------------------------------------
    # Issue 37: Failed Citizen Verification
    # -------------------------------------------------------------
    def test_failed_citizen_verification_requires_reason(self):
        """Rejecting resolution requires a non-empty reason or explanation of what is still wrong."""
        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f"/api/issues/{self.issue.id}/confirm-resolution/", {
            "confirmed": False,
            "reason": "",
            "what_is_still_wrong": ""
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("Reason or explanation of what is still wrong is required", res.data.get('error', ''))

    def test_failed_citizen_verification_reopens_challenge_and_notifies_team(self):
        """Rejecting resolution transitions issue & project to REOPENED and dispatches notifications."""
        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f"/api/issues/{self.issue.id}/confirm-resolution/", {
            "confirmed": False,
            "reason": "Filtration flow rate is extremely low",
            "what_is_still_wrong": "Filter membrane clogged after 2 days of operation.",
            "evidence": "Water TDS reading: 850ppm",
            "photo_video_url": "https://example.com/clogged_membrane.jpg"
        })
        self.assertEqual(res.status_code, 200)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.REOPENED)
        self.assertFalse(self.issue.citizen_verified_resolved)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.REOPENED)

        # Verification record with detailed failure fields
        verif = CitizenVerification.objects.filter(issue=self.issue).first()
        self.assertIsNotNone(verif)
        self.assertEqual(verif.result, CitizenVerification.Result.NOT_RESOLVED)
        self.assertEqual(verif.what_is_still_wrong, "Filter membrane clogged after 2 days of operation.")
        self.assertEqual(verif.photo_video_url, "https://example.com/clogged_membrane.jpg")

        # Notifications dispatched to coordinator, mentor, and student team
        self.assertTrue(Notification.objects.filter(
            recipient=self.coordinator,
            title__icontains="Reopened by Citizen"
        ).exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.mentor,
            title__icontains="Reopened by Citizen"
        ).exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.student,
            title__icontains="Rejected by Citizen"
        ).exists())

    # -------------------------------------------------------------
    # Issue 38: Activity Timeline Querying & Filtering
    # -------------------------------------------------------------
    def test_activity_timeline_filtering(self):
        """Timeline endpoint supports filtering by event_type and object_type."""
        ActivityEvent.objects.create(
            issue=self.issue,
            actor=self.coordinator,
            event_type="open_call_created",
            description="Open call launched",
            object_type="open_call"
        )
        ActivityEvent.objects.create(
            issue=self.issue,
            actor=self.mentor,
            event_type="mentor_assigned",
            description="Mentor assigned to project",
            object_type="mentor"
        )

        res_all = self.client.get(f"/api/issues/{self.issue.id}/activity/")
        self.assertEqual(res_all.status_code, 200)
        self.assertGreaterEqual(len(res_all.data), 2)

        # Filter by event_type
        res_filter = self.client.get(f"/api/issues/{self.issue.id}/activity/?event_type=open_call_created")
        self.assertEqual(res_filter.status_code, 200)
        self.assertTrue(all(e['event_type'] == 'open_call_created' for e in res_filter.data))

        # Filter by object_type
        res_obj = self.client.get(f"/api/issues/{self.issue.id}/activity/?object_type=mentor")
        self.assertEqual(res_obj.status_code, 200)
        self.assertTrue(all(e['object_type'] == 'mentor' for e in res_obj.data))

    # -------------------------------------------------------------
    # Issue 39: Status History Audit Endpoints
    # -------------------------------------------------------------
    def test_challenge_status_history_endpoint(self):
        """GET /api/issues/<id>/status-history/ returns status audit transitions."""
        self.issue.transition_status(Issue.Status.DEPLOYED, actor=self.coordinator, reason="Field installation completed.")

        res = self.client.get(f"/api/issues/{self.issue.id}/status-history/")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.data), 1)
        latest = res.data[0]
        self.assertEqual(latest['new_status'], Issue.Status.DEPLOYED)
        self.assertEqual(latest['reason'], "Field installation completed.")
        self.assertEqual(latest['actor'], self.coordinator.id)

    def test_project_status_history_endpoint(self):
        """GET /api/pitches/projects/<id>/status-history/ returns project lifecycle events."""
        self.project.transition_status(Project.Status.PILOT, actor=self.mentor, reason="Lab testing cleared.")
        self.project.transition_status(Project.Status.DEPLOYMENT_READY, actor=self.student, reason="Field pilot ready.")

        res = self.client.get(f"/api/pitches/projects/{self.project.id}/status-history/")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.data), 2)
        statuses = [e['metadata'].get('new_status') for e in res.data if 'new_status' in e.get('metadata', {})]
        self.assertIn(Project.Status.DEPLOYMENT_READY, statuses)

    # -------------------------------------------------------------
    # Issue 40: Discussion System (Project Discussions)
    # -------------------------------------------------------------
    def test_project_discussion_creation_and_activity_logging(self):
        """Discussions on projects are saved, listed, and logged to challenge activity."""
        self.client.force_authenticate(user=self.mentor)
        res_post = self.client.post(f"/api/pitches/projects/{self.project.id}/discussions/", {
            "content": "Please calibrate the TDS telemetry sensor before running the 48-hour endurance test."
        })
        self.assertEqual(res_post.status_code, 201)
        self.assertEqual(res_post.data['target_type'], 'project')

        # List project discussions
        res_list = self.client.get(f"/api/pitches/projects/{self.project.id}/discussions/")
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.data), 1)
        self.assertEqual(res_list.data[0]['author_details']['name'], self.mentor.name)

        # Activity logged on challenge
        self.assertTrue(ActivityEvent.objects.filter(
            issue=self.issue,
            event_type='PROJECT_DISCUSSION'
        ).exists())

    def test_action_inbox_includes_reopened_challenge_from_failed_verification(self):
        """Action inbox lists citizen_verification_failures for adopting coordinator."""
        self.issue.transition_status(Issue.Status.REOPENED, actor=self.citizen, reason="Citizen verification failed.")

        self.client.force_authenticate(user=self.coordinator)
        res = self.client.get("/api/issues/action-inbox/")
        self.assertEqual(res.status_code, 200)

        failures = res.data['citizen_verification_failures']
        self.assertGreaterEqual(failures['count'], 1)
        failure_ids = [item['id'] for item in failures['items']]
        self.assertIn(self.issue.id, failure_ids)
