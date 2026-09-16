from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.users.models import User, University, Organization
from apps.issues.models import (
    Issue, Adoption, OpenCall, CitizenVerification, ActivityEvent
)
from apps.pitches.models import Pitch, PitchVersionHistory, ProjectLifecycle


class P0Issues5To10TestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Universities
        self.uni_a = University.objects.create(name="BIT Sindri", district="Dhanbad")
        self.uni_b = University.objects.create(name="Ranchi University", district="Ranchi")

        # Organizations
        self.org_tata = Organization.objects.create(name="Tata Steel CSR")

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
        self.student_a = User.objects.create_user(
            email="student_a@bitsindri.ac.in",
            name="Student A",
            role=User.Role.STUDENT,
            university=self.uni_a
        )
        self.student_b = User.objects.create_user(
            email="student_b@ranchi.ac.in",
            name="Student B",
            role=User.Role.STUDENT,
            university=self.uni_b
        )
        self.industry_rep = User.objects.create_user(
            email="industry@tata.com",
            name="Tata Rep",
            role=User.Role.INDUSTRY_PARTNER,
            organization=self.org_tata
        )

        # Baseline Issue: Validated and adopted by Uni A
        self.issue = Issue.objects.create(
            title="Arsenic in Drinking Water",
            description="High arsenic detected in tubewells across village.",
            district="Dhanbad",
            status=Issue.Status.ADOPTED,
            submitted_by=self.citizen,
            photo_url="http://example.com/water.jpg"
        )
        self.adoption = Adoption.objects.create(
            issue=self.issue,
            university=self.uni_a,
            coordinator=self.coord_a,
            mode=Adoption.Mode.SELF_ADOPTED
        )

    def test_issue_6_open_call_lifecycle_and_permissions(self):
        """
        Issue 6: Real OpenCall model and API endpoints.
        - University Coordinator of adopting uni can create an Open Call.
        - Coordinator of non-adopting uni cannot create an Open Call for this issue.
        - Listing and detail views work.
        """
        # 1. Non-adopting coordinator attempts to create Open Call -> Forbidden
        self.client.force_authenticate(user=self.coord_b)
        resp = self.client.post('/api/issues/open-calls/', {
            'issue': self.issue.id,
            'title': 'RU Clean Water Challenge',
            'description': 'Open call for clean water',
            'max_teams': 5,
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Adopting coordinator creates Open Call -> Success (HTTP 201)
        self.client.force_authenticate(user=self.coord_a)
        resp = self.client.post('/api/issues/open-calls/', {
            'issue': self.issue.id,
            'title': 'BIT Sindri Water Innovation Call 2026',
            'description': 'Calling student teams to build low-cost arsenic filtration.',
            'opening_date': '2026-03-01',
            'closing_date': '2026-04-15',
            'eligibility': 'Enrolled engineering students',
            'required_skills': 'Chemical engineering, IoT sensors',
            'departments': 'Chemical, Mechanical',
            'funding': 'INR 50,000 grant per team',
            'evaluation_criteria': 'Cost, sustainability, field test results',
            'max_teams': 8,
            'status': 'open',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        open_call_id = resp.data['id']
        self.assertEqual(resp.data['university'], self.uni_a.id)
        self.assertEqual(resp.data['title'], 'BIT Sindri Water Innovation Call 2026')

        # Verify activity was logged (Issue 8)
        event = ActivityEvent.objects.filter(issue=self.issue, event_type='open_call_created').first()
        self.assertIsNotNone(event)
        self.assertIn('BIT Sindri', event.description)

        # 3. List Open Calls filterable by issue
        self.client.force_authenticate(user=self.student_a)
        list_resp = self.client.get(f'/api/issues/open-calls/?issue={self.issue.id}')
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_resp.data), 1)
        self.assertEqual(list_resp.data[0]['id'], open_call_id)

        # 4. Detail view
        detail_resp = self.client.get(f'/api/issues/open-calls/{open_call_id}/')
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data['max_teams'], 8)

        # 5. Non-coordinator cannot update
        self.client.force_authenticate(user=self.student_a)
        upd_resp = self.client.patch(f'/api/issues/open-calls/{open_call_id}/', {'max_teams': 10})
        self.assertEqual(upd_resp.status_code, status.HTTP_403_FORBIDDEN)

        # Coordinator can update
        self.client.force_authenticate(user=self.coord_a)
        upd_resp = self.client.patch(f'/api/issues/open-calls/{open_call_id}/', {'max_teams': 12})
        self.assertEqual(upd_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(upd_resp.data['max_teams'], 12)

    def test_issue_7_and_9_request_changes_and_pitch_version_history(self):
        """
        Issue 7: Review Board request changes workflow.
        Issue 9: Pitch version history and hash calculation.
        """
        # Create an Open Call first
        open_call = OpenCall.objects.create(
            issue=self.issue,
            university=self.uni_a,
            created_by=self.coord_a,
            title="Water Pitch Call",
            description="Call desc",
            status=OpenCall.Status.OPEN
        )

        # Student A creates a pitch linked to open call
        self.client.force_authenticate(user=self.student_a)
        create_resp = self.client.post('/api/pitches/', {
            'issue': self.issue.id,
            'open_call': open_call.id,
            'title': 'Solar Powered Arsenic Filter',
            'public_summary': 'Uses graphene membrane with solar backwash.',
            'confidential_package': 'Full confidential architecture v1 specification.',
        })
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        pitch_id = create_resp.data['id']

        pitch = Pitch.objects.get(id=pitch_id)
        self.assertEqual(pitch.version, 1)
        self.assertTrue(bool(pitch.submission_hash))

        # Check that initial snapshot history was created
        v1_history = PitchVersionHistory.objects.filter(pitch=pitch, version=1).first()
        self.assertIsNotNone(v1_history)
        self.assertEqual(v1_history.change_summary, 'Initial proposal submission')
        self.assertEqual(v1_history.submission_hash, pitch.submission_hash)

        # Move pitch to under_review so review board can act
        pitch.status = Pitch.Status.UNDER_REVIEW
        pitch.save()

        # Review Board (Coordinator) requests changes
        self.client.force_authenticate(user=self.coord_a)
        action_resp = self.client.post(f'/api/pitches/{pitch_id}/review-action/', {
            'action': 'request_changes',
            'review_feedback': 'Please include laboratory chemical analysis of graphene membrane durability.',
        })
        self.assertEqual(action_resp.status_code, status.HTTP_200_OK)
        pitch.refresh_from_db()
        self.assertEqual(pitch.status, Pitch.Status.CHANGES_REQUESTED)
        self.assertIn('graphene membrane durability', pitch.review_feedback)

        # Verify activity timeline contains the CHANGES_REQUESTED event (Issue 8)
        timeline_resp = self.client.get(f'/api/issues/{self.issue.id}/activity/')
        self.assertEqual(timeline_resp.status_code, status.HTTP_200_OK)
        event_types = [e['event_type'] for e in timeline_resp.data]
        self.assertIn('CHANGES_REQUESTED', event_types)

        # Other student cannot resubmit
        self.client.force_authenticate(user=self.student_b)
        resubmit_fail = self.client.post(f'/api/pitches/{pitch_id}/resubmit/', {
            'title': 'Hijacked pitch',
            'public_summary': 'Bad',
            'confidential_package': 'Bad proposal',
            'change_summary': 'Unauthorized modification'
        })
        self.assertEqual(resubmit_fail.status_code, status.HTTP_403_FORBIDDEN)

        # Student A resubmits with updated proposal and change summary
        self.client.force_authenticate(user=self.student_a)
        resubmit_resp = self.client.post(f'/api/pitches/{pitch_id}/resubmit/', {
            'title': 'Solar Powered Arsenic Filter (Revised)',
            'public_summary': 'Uses tested graphene membrane with solar backwash.',
            'confidential_package': 'Full confidential architecture v2 specification with verified lab analysis.',
            'change_summary': 'Added 30-day lab durability test results and revised budget.',
        })
        self.assertEqual(resubmit_resp.status_code, status.HTTP_200_OK)
        pitch.refresh_from_db()
        self.assertEqual(pitch.status, Pitch.Status.RESUBMITTED)
        self.assertEqual(pitch.version, 2)
        self.assertEqual(pitch.title, 'Solar Powered Arsenic Filter (Revised)')

        # Verify version history has v2
        v2_history = PitchVersionHistory.objects.filter(pitch=pitch, version=2).first()
        self.assertIsNotNone(v2_history)
        self.assertEqual(v2_history.change_summary, 'Added 30-day lab durability test results and revised budget.')
        self.assertEqual(v2_history.confidential_package, 'Full confidential architecture v2 specification with verified lab analysis.')
        self.assertNotEqual(v2_history.submission_hash, v1_history.submission_hash)

        # PitchDetailView includes version_history
        detail_resp = self.client.get(f'/api/pitches/{pitch_id}/')
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(detail_resp.data['version_history']), 2)

    def test_issue_5_and_10_deployment_to_citizen_verification_gate(self):
        """
        Issue 5: Canonical state machine transitions (DEPLOYED -> AWAITING_VERIFICATION -> RESOLVED / REOPENED).
        Issue 10: Mandatory citizen verification gate.
        """
        # Pitch approved and in milestone development
        pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.uni_a,
            title='Water Filter Deployment',
            public_summary='Deploying filter units',
            confidential_package='Deployment plan',
            status=Pitch.Status.SELECTED
        )
        pitch.student_team.add(self.student_a)
        lifecycle = ProjectLifecycle.objects.create(
            pitch=pitch,
            milestones=[
                {'id': 1, 'title': 'Design Freeze', 'completed': True},
                {'id': 2, 'title': 'Field Pilot Deployment', 'completed': True}
            ]
        )

        # Student submits milestone update marking outcome as 'deployed'
        self.client.force_authenticate(user=self.student_a)
        upd_resp = self.client.post(f'/api/pitches/lifecycle/{lifecycle.id}/update/', {
            'outcome_status': 'deployed',
            'test_results': '10 water filter units deployed in village sector 4.'
        })
        self.assertEqual(upd_resp.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        # Challenge status MUST be AWAITING_VERIFICATION, NOT directly RESOLVED!
        self.assertEqual(self.issue.status, Issue.Status.AWAITING_VERIFICATION)
        self.assertFalse(self.issue.citizen_verified_resolved)

        # Non-submitter cannot confirm resolution
        self.client.force_authenticate(user=self.student_b)
        confirm_fail = self.client.post(f'/api/issues/{self.issue.id}/confirm-resolution/', {
            'confirmed': True,
            'feedback': 'Impersonating citizen'
        })
        self.assertEqual(confirm_fail.status_code, status.HTTP_403_FORBIDDEN)

        # Original Citizen confirms resolution with feedback and evidence
        self.client.force_authenticate(user=self.citizen)
        confirm_resp = self.client.post(f'/api/issues/{self.issue.id}/confirm-resolution/', {
            'confirmed': True,
            'feedback': 'The water is now clear, tested negative for arsenic! Thank you team.',
            'evidence': 'http://example.com/clean_water_test_report.pdf'
        })
        self.assertEqual(confirm_resp.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.RESOLVED)
        self.assertTrue(self.issue.citizen_verified_resolved)
        self.assertEqual(self.issue.citizen_feedback_on_resolution, 'The water is now clear, tested negative for arsenic! Thank you team.')

        # Verify CitizenVerification record was created (Issue 10)
        verification = CitizenVerification.objects.filter(issue=self.issue, citizen=self.citizen).first()
        self.assertIsNotNone(verification)
        self.assertEqual(verification.result, CitizenVerification.Result.VERIFIED)
        self.assertEqual(verification.evidence, 'http://example.com/clean_water_test_report.pdf')

        # Verify timeline has both project deployment and citizen verification events (Issue 8)
        timeline_resp = self.client.get(f'/api/issues/{self.issue.id}/activity/')
        self.assertEqual(timeline_resp.status_code, status.HTTP_200_OK)
        event_types = [e['event_type'] for e in timeline_resp.data]
        self.assertIn('PROJECT_DEPLOYED', event_types)
        self.assertIn('citizen_verification', event_types)

    def test_citizen_reopens_unresolved_issue(self):
        """
        When the citizen reports the issue is NOT resolved, the challenge status must become REOPENED.
        """
        self.issue.status = Issue.Status.AWAITING_VERIFICATION
        self.issue.save()

        self.client.force_authenticate(user=self.citizen)
        confirm_resp = self.client.post(f'/api/issues/{self.issue.id}/confirm-resolution/', {
            'confirmed': False,
            'feedback': 'Water still smells metallic and test kit still shows arsenic traces.',
        })
        self.assertEqual(confirm_resp.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.REOPENED)
        self.assertFalse(self.issue.citizen_verified_resolved)

        verification = CitizenVerification.objects.filter(issue=self.issue, citizen=self.citizen).first()
        self.assertIsNotNone(verification)
        self.assertEqual(verification.result, CitizenVerification.Result.NOT_RESOLVED)
