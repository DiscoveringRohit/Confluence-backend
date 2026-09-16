from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models import User, University, Organization
from apps.issues.models import Issue, Adoption, StudentNomination, IssueStatusHistory
from apps.pitches.models import Pitch
from apps.engagements.models import IndustryEngagement


class P0WorkflowIssuesTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Universities
        self.uni_a = University.objects.create(name="BIT Sindri", district="Dhanbad")
        self.uni_b = University.objects.create(name="Ranchi University", district="Ranchi")

        # Organizations
        self.org_tata = Organization.objects.create(name="Tata Steel CSR")
        self.org_sail = Organization.objects.create(name="SAIL Bokaro")

        # Users
        self.citizen = User.objects.create_user(
            email="citizen@jharkhand.in",
            name="Citizen Ramesh",
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
        self.mentor_a = User.objects.create_user(
            email="mentor_a@bitsindri.ac.in",
            name="Prof Sharma",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni_a
        )
        self.mentor_b = User.objects.create_user(
            email="mentor_b@ranchi.ac.in",
            name="Prof Verma",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni_b
        )
        self.student_a1 = User.objects.create_user(
            email="student_a1@bitsindri.ac.in",
            name="Student A1",
            role=User.Role.STUDENT,
            university=self.uni_a
        )
        self.student_a2 = User.objects.create_user(
            email="student_a2@bitsindri.ac.in",
            name="Student A2",
            role=User.Role.STUDENT,
            university=self.uni_a
        )
        self.student_b1 = User.objects.create_user(
            email="student_b1@ranchi.ac.in",
            name="Student B1",
            role=User.Role.STUDENT,
            university=self.uni_b
        )
        self.industry_tata = User.objects.create_user(
            email="partner@tatasteel.com",
            name="Tata CSR Lead",
            role=User.Role.INDUSTRY_PARTNER,
            organization=self.org_tata
        )
        self.industry_sail = User.objects.create_user(
            email="partner@sail.in",
            name="SAIL Lead",
            role=User.Role.INDUSTRY_PARTNER,
            organization=self.org_sail
        )
        self.gov_admin = User.objects.create_user(
            email="admin@jharkhand.gov.in",
            name="Gov Admin",
            role=User.Role.GOV_ADMIN,
            is_staff=True
        )

    # =========================================================================
    # ISSUE 1: University ownership enforcement
    # =========================================================================
    def test_issue_1_adoption_records_coordinator(self):
        """When a university coordinator adopts an issue, the coordinator user is explicitly saved."""
        issue = Issue.objects.create(
            title="Arsenic in Topchanchi water",
            description="High arsenic detected in village wells",
            expected_outcome="Filtration units",
            district="Dhanbad",
            photo_url="https://example.com/water.jpg",
            status=Issue.Status.VALIDATED,
            submitted_by=self.citizen
        )

        self.client.force_authenticate(user=self.coord_a)
        res = self.client.post(f"/api/issues/{issue.id}/adopt/")
        self.assertEqual(res.status_code, 201)

        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.ADOPTED)
        self.assertIsNotNone(issue.adoption)
        self.assertEqual(issue.adoption.coordinator, self.coord_a)
        self.assertEqual(issue.adoption.university, self.uni_a)
        self.assertEqual(issue.adoption.status, Adoption.Status.APPROVED)

    def test_issue_1_unauthorized_user_cannot_edit_issue(self):
        """Arbitrary authenticated users cannot edit issues; citizens can only edit while SUBMITTED."""
        issue = Issue.objects.create(
            title="Solar unit broken",
            description="Broken inverter",
            expected_outcome="Replacement",
            district="Dhanbad",
            photo_url="https://example.com/solar.jpg",
            status=Issue.Status.VALIDATED,
            submitted_by=self.citizen
        )

        # Student B1 cannot edit
        self.client.force_authenticate(user=self.student_b1)
        res = self.client.patch(f"/api/issues/{issue.id}/", {"title": "Hacked Title"})
        self.assertEqual(res.status_code, 403)

        # Citizen cannot edit after it is already VALIDATED
        self.client.force_authenticate(user=self.citizen)
        res = self.client.patch(f"/api/issues/{issue.id}/", {"title": "Citizen Edited Title"})
        self.assertEqual(res.status_code, 403)

        # But citizen CAN edit while still SUBMITTED
        issue.status = Issue.Status.SUBMITTED
        issue.save()
        res = self.client.patch(f"/api/issues/{issue.id}/", {"title": "Citizen Updated Title"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['title'], "Citizen Updated Title")

    # =========================================================================
    # ISSUE 2: Student-university challenge validation
    # =========================================================================
    def test_issue_2_student_cannot_pitch_to_unadopted_or_other_university_issue(self):
        """Student cannot submit pitch to an issue not adopted by their university."""
        issue = Issue.objects.create(
            title="Fluoride filtration in Topchanchi",
            description="Needs membrane",
            expected_outcome="Purified water",
            district="Dhanbad",
            photo_url="https://example.com/water.jpg",
            status=Issue.Status.ADOPTED,
            submitted_by=self.citizen
        )
        Adoption.objects.create(
            issue=issue,
            university=self.uni_a,
            coordinator=self.coord_a,
            mode=Adoption.Mode.SELF_ADOPTED
        )

        # Student B1 from Ranchi University attempts to submit pitch to BIT Sindri's adopted issue
        self.client.force_authenticate(user=self.student_b1)
        res = self.client.post("/api/pitches/", {
            "issue": issue.id,
            "title": "Cross-Uni Unauthorized Proposal",
            "public_summary": "Summary text",
            "confidential_package": "Secret details"
        })
        self.assertIn(res.status_code, [400, 403])

        # Student A1 from BIT Sindri submits pitch: SUCCESS
        self.client.force_authenticate(user=self.student_a1)
        res = self.client.post("/api/pitches/", {
            "issue": issue.id,
            "title": "BIT Sindri Alumina Filter",
            "public_summary": "Activated alumina filter",
            "confidential_package": "Secret formula",
            "team_member_ids": [self.student_a2.id]
        })
        self.assertEqual(res.status_code, 201)

    def test_issue_2_student_cannot_include_team_member_from_other_university(self):
        """Student pitch cannot include collaborators from unrelated universities."""
        issue = Issue.objects.create(
            title="Bio-digester for dairy waste",
            description="Methane recovery",
            expected_outcome="Cooking gas",
            district="Dhanbad",
            photo_url="https://example.com/bio.jpg",
            status=Issue.Status.ADOPTED,
            submitted_by=self.citizen
        )
        Adoption.objects.create(
            issue=issue,
            university=self.uni_a,
            coordinator=self.coord_a
        )

        self.client.force_authenticate(user=self.student_a1)
        res = self.client.post("/api/pitches/", {
            "issue": issue.id,
            "title": "Bio-digester plan",
            "public_summary": "Summary",
            "confidential_package": "Confidential",
            "team_member_ids": [self.student_b1.id]  # student_b1 is from uni_b
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("team_member_ids", str(res.data))

    # =========================================================================
    # ISSUE 3: Mentor-university validation
    # =========================================================================
    def test_issue_3_cannot_assign_mentor_from_different_university(self):
        """Review board coordinator can only assign mentors from their own maintaining university."""
        issue = Issue.objects.create(
            title="Microgrid load balancer",
            description="Grid balancing in rural villages",
            expected_outcome="24/7 power",
            district="Dhanbad",
            photo_url="https://example.com/power.jpg",
            status=Issue.Status.ADOPTED,
            submitted_by=self.citizen
        )
        Adoption.objects.create(issue=issue, university=self.uni_a, coordinator=self.coord_a)

        pitch = Pitch.objects.create(
            issue=issue,
            university=self.uni_a,
            title="Smart Inverter",
            public_summary="Inverter summary",
            confidential_package="Inverter IP"
        )
        pitch.student_team.add(self.student_a1)

        self.client.force_authenticate(user=self.coord_a)

        # Attempt to assign mentor_b (from Ranchi University) to BIT Sindri pitch
        res = self.client.post(f"/api/pitches/{pitch.id}/review-action/", {
            "action": "assign_mentor",
            "mentor_id": self.mentor_b.id
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("maintaining university", res.data.get('error', ''))

        # Assign mentor_a (from BIT Sindri)
        res = self.client.post(f"/api/pitches/{pitch.id}/review-action/", {
            "action": "assign_mentor",
            "mentor_id": self.mentor_a.id
        })
        self.assertEqual(res.status_code, 200)
        pitch.refresh_from_db()
        self.assertEqual(pitch.assigned_mentor, self.mentor_a)

    # =========================================================================
    # ISSUE 4: Industry engagement authorization
    # =========================================================================
    def test_issue_4_industry_engagement_participant_authorization(self):
        """Only the appropriate counterpart can accept/decline; only participants can activate/complete."""
        issue = Issue.objects.create(
            title="Industrial Slag Reuse in Road Construction",
            description="Using blast furnace slag",
            expected_outcome="Low cost roads",
            district="Dhanbad",
            photo_url="https://example.com/slag.jpg",
            status=Issue.Status.ADOPTED,
            submitted_by=self.citizen
        )
        Adoption.objects.create(issue=issue, university=self.uni_a, coordinator=self.coord_a)

        # Industry (Tata) proposes engagement to University
        engagement = IndustryEngagement.objects.create(
            issue=issue,
            industry_org=self.org_tata,
            created_by=self.industry_tata,
            initiator=IndustryEngagement.Initiator.INDUSTRY,
            engagement_type=IndustryEngagement.EngagementType.FUNDING,
            status=IndustryEngagement.Status.REQUESTED,
            proposal_notes="We offer ₹5,00,000 CSR funding for pilot"
        )

        # Random student or SAIL partner cannot accept
        self.client.force_authenticate(user=self.student_a1)
        res = self.client.post(f"/api/engagements/{engagement.id}/respond/", {"action": "accept"})
        self.assertEqual(res.status_code, 403)

        self.client.force_authenticate(user=self.industry_sail)
        res = self.client.post(f"/api/engagements/{engagement.id}/respond/", {"action": "accept"})
        self.assertEqual(res.status_code, 403)

        # Coordinator of adopting university (BIT Sindri) accepts: SUCCESS
        self.client.force_authenticate(user=self.coord_a)
        res = self.client.post(f"/api/engagements/{engagement.id}/respond/", {
            "action": "accept",
            "response_notes": "Accepted! MOU sent."
        })
        self.assertEqual(res.status_code, 200)
        engagement.refresh_from_db()
        self.assertEqual(engagement.status, IndustryEngagement.Status.ACCEPTED)

        # Unrelated coordinator (Ranchi Uni) cannot activate
        self.client.force_authenticate(user=self.coord_b)
        res = self.client.post(f"/api/engagements/{engagement.id}/respond/", {"action": "activate"})
        self.assertEqual(res.status_code, 403)

        # Participating Industry partner activates: SUCCESS
        self.client.force_authenticate(user=self.industry_tata)
        res = self.client.post(f"/api/engagements/{engagement.id}/respond/", {"action": "activate"})
        self.assertEqual(res.status_code, 200)
        engagement.refresh_from_db()
        self.assertEqual(engagement.status, IndustryEngagement.Status.ACTIVE)

    # =========================================================================
    # ISSUE 5: Canonical challenge state machine & history
    # =========================================================================
    def test_issue_5_canonical_state_machine_and_status_history(self):
        """Verify status history audit trail and citizen failure reopening workflow."""
        # 1. Citizen creates issue
        self.client.force_authenticate(user=self.citizen)
        res = self.client.post("/api/issues/", {
            "title": "Solar Water Pump Malfunction",
            "description": "Burnt motor coil in Kasmar block",
            "expected_outcome": "Replace motor and solar wiring",
            "district": "Bokaro",
            "photo_url": "https://example.com/pump.jpg"
        })
        self.assertEqual(res.status_code, 201)
        issue_id = res.data['id']
        issue = Issue.objects.get(id=issue_id)
        self.assertEqual(issue.status, Issue.Status.SUBMITTED)

        # Verify initial history logged
        history = IssueStatusHistory.objects.filter(issue=issue)
        self.assertTrue(history.filter(new_status=Issue.Status.SUBMITTED).exists())

        # 2. Moderator validates issue
        self.client.force_authenticate(user=self.gov_admin)
        res = self.client.post(f"/api/issues/{issue.id}/moderate/", {
            "action": "validate",
            "notes": "Verified by Block Development Officer"
        })
        self.assertEqual(res.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.VALIDATED)
        self.assertTrue(IssueStatusHistory.objects.filter(issue=issue, new_status=Issue.Status.VALIDATED).exists())

        # 3. University adopts issue
        self.client.force_authenticate(user=self.coord_a)
        res = self.client.post(f"/api/issues/{issue.id}/adopt/")
        self.assertEqual(res.status_code, 201)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.ADOPTED)
        self.assertTrue(IssueStatusHistory.objects.filter(issue=issue, new_status=Issue.Status.ADOPTED).exists())

        # 4. Student pitches and University selects winner -> ASSIGNED
        pitch = Pitch.objects.create(
            issue=issue,
            university=self.uni_a,
            title="Pump Rewinding & IoT Monitor",
            public_summary="Summary",
            confidential_package="Secret"
        )
        pitch.student_team.add(self.student_a1)

        res = self.client.post(f"/api/pitches/{pitch.id}/review-action/", {
            "action": "select_winner",
            "review_feedback": "Approved by faculty panel."
        })
        self.assertEqual(res.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.ASSIGNED)
        self.assertTrue(IssueStatusHistory.objects.filter(issue=issue, new_status=Issue.Status.ASSIGNED).exists())

        # 5. Citizen verification failure -> transitions to REOPENED
        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f"/api/issues/{issue.id}/confirm-resolution/", {
            "confirmed": False,
            "feedback": "The motor was replaced but water pump is still not lifting water to tank."
        })
        self.assertEqual(res.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.REOPENED)
        self.assertFalse(issue.citizen_verified_resolved)

        reopened_history = IssueStatusHistory.objects.filter(issue=issue, new_status=Issue.Status.REOPENED).first()
        self.assertIsNotNone(reopened_history)
        self.assertIn("not lifting water", reopened_history.reason)

        # 6. Citizen confirms resolution -> transitions to RESOLVED
        res = self.client.post(f"/api/issues/{issue.id}/confirm-resolution/", {
            "confirmed": True,
            "feedback": "Piping issue fixed. Water is flowing smoothly!"
        })
        self.assertEqual(res.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.RESOLVED)
        self.assertTrue(issue.citizen_verified_resolved)

        resolved_history = IssueStatusHistory.objects.filter(issue=issue, new_status=Issue.Status.RESOLVED).first()
        self.assertIsNotNone(resolved_history)
        self.assertIn("Water is flowing smoothly", resolved_history.reason)
