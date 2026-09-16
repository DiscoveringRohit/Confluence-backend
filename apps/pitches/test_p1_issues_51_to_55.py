from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.issues.models import Issue, Adoption, StudentNomination
from apps.pitches.models import Pitch, Project, ProjectMilestone, Certificate
from apps.engagements.models import IndustryEngagement
from apps.notifications.models import Notification
from apps.users.models import University, Organization

User = get_user_model()


class Issues51To55TestCase(TestCase):
    """
    Test suite for Issues 51 to 55 from Confluence Workflow Gap Analysis:
    - Issue 51: Industry Workflow (Inside Project Context & Express Interest)
    - Issue 52: Notification System for key lifecycle events
    - Issue 53: Deterministic Notification Identity & Idempotent Deduplication (event_id)
    - Issue 54: Real Database Aggregations for Reports & Analytics
    - Issue 55: Verified Outcome Certificates & Cryptographic Verification
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Setup Universities & Organizations
        self.univ = University.objects.create(
            name="Delhi Technological University",
            code="DTU",
            district="North West Delhi"
        )
        self.org_tata = Organization.objects.create(
            name="Tata Power Renewable",
            website="https://tatapower.com",
            org_type="industry"
        )

        # 2. Setup Users
        self.citizen = User.objects.create_user(
            email="citizen@delhi.gov.in",
            password="password123",
            name="Ramesh Sharma",
            role="citizen"
        )
        self.student = User.objects.create_user(
            email="student@dtu.ac.in",
            password="password123",
            name="Aman Gupta",
            role="student",
            university=self.univ
        )
        self.mentor = User.objects.create_user(
            email="mentor@dtu.ac.in",
            password="password123",
            name="Dr. Rajesh Rao",
            role="faculty_mentor",
            university=self.univ
        )
        self.coordinator = User.objects.create_user(
            email="coord@dtu.ac.in",
            password="password123",
            name="Prof. Verma",
            role="university_coordinator",
            university=self.univ
        )
        self.industry_rep = User.objects.create_user(
            email="partner@tatapower.com",
            password="password123",
            name="Tata Rep",
            role="industry_partner",
            organization=self.org_tata
        )
        self.gov_admin = User.objects.create_user(
            email="admin@delhi.gov.in",
            password="password123",
            name="Director Delhi Gov",
            role="gov_admin",
            is_staff=True
        )

        # 3. Setup Challenge & Adoption
        self.issue = Issue.objects.create(
            title="Solar Microgrid Inverter Phase Desynchronization",
            description="Grid sync instability during peak morning solar load.",
            submitted_by=self.citizen,
            district="North West Delhi",
            category="ENERGY",
            status=Issue.Status.ADOPTED,
            maintaining_university=self.univ
        )
        self.adoption = Adoption.objects.create(
            issue=self.issue,
            university=self.univ,
            coordinator=self.coordinator,
            status=Adoption.Status.APPROVED
        )

        # 4. Setup Solution & Project
        self.pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.univ,
            title="Adaptive PLL Inverter Controller",
            public_summary="Real-time phase locked loop firmware.",
            confidential_package="Proprietary PLL algorithm and RTL code.",
            status=Pitch.Status.SELECTED
        )
        self.pitch.student_team.add(self.student)

        self.project = Project.objects.create(
            solution=self.pitch,
            challenge=self.issue,
            university=self.univ,
            mentor=self.mentor,
            title="Badarpur Solar Microgrid Modernization",
            status=Project.Status.PROTOTYPE
        )
        self.project.team.add(self.student)

    # -------------------------------------------------------------------------
    # Issue 51: Industry Workflow inside Project Context
    # -------------------------------------------------------------------------
    def test_issue_51_project_express_interest(self):
        """Industry partner can express interest directly on an active project."""
        self.client.force_authenticate(user=self.industry_rep)
        res = self.client.post(f'/api/pitches/projects/{self.project.id}/express-interest/', {
            'engagement_type': IndustryEngagement.EngagementType.PROTOTYPING,
            'proposal_notes': 'Offering high-voltage hardware lab access and pilot testbed.'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['project'], self.project.id)
        self.assertEqual(res.data['status'], IndustryEngagement.Status.REQUESTED)
        self.assertEqual(res.data['initiator'], IndustryEngagement.Initiator.INDUSTRY)

        engagement = IndustryEngagement.objects.get(id=res.data['id'])
        self.assertEqual(engagement.project, self.project)
        self.assertEqual(engagement.issue, self.issue)

        # Student or citizen cannot express industry interest -> 403
        self.client.force_authenticate(user=self.student)
        res_forbidden = self.client.post(f'/api/pitches/projects/{self.project.id}/express-interest/', {})
        self.assertEqual(res_forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_issue_51_project_scoped_engagements_list(self):
        """GET /api/pitches/projects/<id>/engagements/ lists engagements for that specific project."""
        # Create engagement for this project
        IndustryEngagement.objects.create(
            issue=self.issue,
            pitch=self.pitch,
            project=self.project,
            industry_org=self.org_tata,
            created_by=self.industry_rep,
            initiator=IndustryEngagement.Initiator.INDUSTRY,
            status=IndustryEngagement.Status.REQUESTED,
            proposal_notes="Hardware testing support."
        )

        self.client.force_authenticate(user=self.coordinator)
        res = self.client.get(f'/api/pitches/projects/{self.project.id}/engagements/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        engagements_data = res.data.get('results', res.data) if isinstance(res.data, dict) else res.data
        self.assertEqual(len(engagements_data), 1)
        self.assertEqual(engagements_data[0]['project'], self.project.id)

    # -------------------------------------------------------------------------
    # Issue 52: Notification System for key lifecycle events
    # -------------------------------------------------------------------------
    def test_issue_52_lifecycle_notification_triggers(self):
        """Notifications are dispatched on student nomination approval and project field transitions."""
        # 1. Nomination approval notification
        nomination = StudentNomination.objects.create(
            issue=self.issue,
            student=self.student,
            university=self.univ,
            rationale="We have domain expertise in microgrid power electronics."
        )
        nomination.status = StudentNomination.Status.APPROVED
        nomination.save()

        notif_nom = Notification.objects.filter(
            recipient=self.student,
            event_id=f"nomination_{nomination.id}_approved"
        ).first()
        self.assertIsNotNone(notif_nom)
        self.assertIn("Nomination Approved", notif_nom.title)

        # 2. Project field deployment notification
        self.project.status = Project.Status.DEPLOYED
        self.project.save()

        notif_team = Notification.objects.filter(
            recipient=self.student,
            event_id=f"project_{self.project.id}_deployed_{self.student.id}"
        ).first()
        self.assertIsNotNone(notif_team)
        self.assertIn("Field Deployment Completed", notif_team.title)

        notif_citizen = Notification.objects.filter(
            recipient=self.citizen,
            event_id=f"project_{self.project.id}_citizen_verify_{self.citizen.id}"
        ).first()
        self.assertIsNotNone(notif_citizen)
        self.assertIn("Verification Requested", notif_citizen.title)

    # -------------------------------------------------------------------------
    # Issue 53: Deterministic Notification Identity & Idempotency
    # -------------------------------------------------------------------------
    def test_issue_53_notification_idempotency_via_event_id(self):
        """Notification.send_notification deduplicates by (recipient, event_id)."""
        event_key = "unique_milestone_event_123"
        notif1, created1 = Notification.send_notification(
            recipient=self.student,
            title="Milestone Approved",
            message="Test milestone approved.",
            notification_type=Notification.NotificationType.PROJECT,
            event_id=event_key
        )
        self.assertTrue(created1)

        # Re-trigger with same event key
        notif2, created2 = Notification.send_notification(
            recipient=self.student,
            title="Milestone Approved",
            message="Test milestone approved.",
            notification_type=Notification.NotificationType.PROJECT,
            event_id=event_key
        )
        self.assertFalse(created2)
        self.assertEqual(notif1.id, notif2.id)
        self.assertEqual(Notification.objects.filter(recipient=self.student, event_id=event_key).count(), 1)

    def test_issue_53_signal_event_id_deduplication(self):
        """Saving a project multiple times in the same status does not spawn duplicate notifications."""
        self.project.status = Project.Status.PILOT
        self.project.save()
        self.project.save()  # Second save (e.g. metadata change)

        pilot_event_id = f"project_{self.project.id}_pilot_{self.student.id}"
        count = Notification.objects.filter(recipient=self.student, event_id=pilot_event_id).count()
        self.assertEqual(count, 1)

    # -------------------------------------------------------------------------
    # Issue 54: Real Database Aggregations for Reports & Analytics
    # -------------------------------------------------------------------------
    def test_issue_54_analytics_real_database_aggregations(self):
        """Analytics summary returns real database metrics without placeholder/mock numbers."""
        self.client.force_authenticate(user=self.gov_admin)
        res = self.client.get('/api/analytics/summary/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.data
        overview = data['overview']
        self.assertTrue(overview.get('is_real_time_aggregate'))
        self.assertGreaterEqual(overview['total_projects'], 1)
        self.assertEqual(overview['projects_prototype'], 1)
        self.assertIn('categories', data)
        self.assertIn('institutional_track_record', data)

    def test_issue_54_analytics_student_access_control(self):
        """Students are not permitted to access Government Analytics (403 Forbidden)."""
        self.client.force_authenticate(user=self.student)
        res = self.client.get('/api/analytics/summary/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # Issue 55: Verified Outcome Certificates & Verification
    # -------------------------------------------------------------------------
    def test_issue_55_certificate_generation_blocked_if_unverified(self):
        """Generating certificates for unverified projects returns 400 with missing criteria."""
        self.client.force_authenticate(user=self.coordinator)
        # Project is currently in PROTOTYPE status and has no deployment evidence
        res = self.client.post(f'/api/pitches/projects/{self.project.id}/certificates/generate/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res.data['eligible'])
        self.assertIn('missing_criteria', res.data)
        self.assertGreater(len(res.data['missing_criteria']), 0)

    def test_issue_55_certificate_generation_succeeds_when_verified(self):
        """When all 4 criteria are fulfilled, certificates are generated with SHA-256 seals."""
        # 1. Solution selected (already SELECTED)
        # 2. Project completed / deployed
        self.project.status = Project.Status.VERIFIED
        # 3. Deployment evidence provided
        self.project.deployment_evidence = "NABL lab test report #9042 & telemetry stream verified."
        self.project.save()
        # 4. Citizen verification completed
        self.issue.citizen_verified_resolved = True
        self.issue.save()

        self.client.force_authenticate(user=self.coordinator)
        res = self.client.post(f'/api/pitches/projects/{self.project.id}/certificates/generate/')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('certificates', res.data)
        certs = res.data['certificates']
        self.assertGreaterEqual(len(certs), 1)

        cert_data = certs[0]
        self.assertTrue(cert_data['certificate_id'].startswith("CONF-"))
        self.assertIsNotNone(cert_data['verification_hash'])
        self.assertEqual(len(cert_data['verification_hash']), 64)  # Valid SHA-256 length

        # Verify Certificate model stored in database
        self.assertTrue(Certificate.objects.filter(project=self.project, recipient=self.student).exists())

    def test_issue_55_public_certificate_verification(self):
        """Public verification endpoint confirms authentic certificates and detects revoked ones."""
        # Setup verified project and certificate
        self.project.status = Project.Status.VERIFIED
        self.project.deployment_evidence = "Telemetry verified."
        self.project.save()
        self.issue.citizen_verified_resolved = True
        self.issue.save()

        cert = Certificate.objects.create(
            certificate_id="CONF-2026-TESTVERIFY",
            recipient=self.student,
            project=self.project,
            challenge=self.issue,
            solution=self.pitch,
            role=Certificate.Role.STUDENT_INNOVATOR,
            verification_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

        # 1. Unauthenticated public verification -> 200 OK & authentic
        unauth_client = APIClient()
        res_verify = unauth_client.get(f'/api/pitches/certificates/{cert.certificate_id}/verify/')
        self.assertEqual(res_verify.status_code, status.HTTP_200_OK)
        self.assertTrue(res_verify.data['valid'])
        self.assertEqual(res_verify.data['status'], 'authentic')
        self.assertEqual(res_verify.data['verification']['hash'], cert.verification_hash)

        # 2. Invalid certificate ID -> 404 Not Found
        res_invalid = unauth_client.get('/api/pitches/certificates/CONF-FAKE-99999/verify/')
        self.assertEqual(res_invalid.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(res_invalid.data['valid'])

        # 3. Revoked certificate -> valid: False, status: revoked
        cert.is_revoked = True
        cert.revocation_reason = "Academic integrity revision."
        cert.save()

        res_revoked = unauth_client.get(f'/api/pitches/certificates/{cert.certificate_id}/verify/')
        self.assertEqual(res_revoked.status_code, status.HTTP_200_OK)
        self.assertFalse(res_revoked.data['valid'])
        self.assertEqual(res_revoked.data['status'], 'revoked')
        self.assertEqual(res_revoked.data['revocation_reason'], "Academic integrity revision.")
