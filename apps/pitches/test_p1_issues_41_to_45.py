from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.issues.models import (
    Issue, Adoption, StudentNomination, DiscussionComment,
    ChallengeCollaborator, ActivityEvent
)
from apps.pitches.models import Pitch
from apps.users.models import University

User = get_user_model()


class Issues41To45TestCase(TestCase):
    """
    Test suite for Issues 41 to 45 from Confluence Workflow Gap Analysis:
    - Issue 41: Challenge vs Solution Discussion separation with categories
    - Issue 42: Authoritative Challenge Ownership model (Citizen, Authority, University, Coordinator)
    - Issue 43: ChallengeCollaborator model and role-based management
    - Issue 44: Deep-Link / Refresh independent resolution
    - Issue 45: Canonical Frontend/Backend Status Contract
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Setup Universities
        self.univ_a = University.objects.create(
            name="Delhi Technological University",
            code="DTU",
            district="North West Delhi"
        )
        self.univ_b = University.objects.create(
            name="Anna University",
            code="AU",
            district="Chennai"
        )

        # 2. Setup Users
        self.citizen = User.objects.create_user(
            email="citizen@delhi.gov.in",
            password="password123",
            name="Citizen Ramesh",
            role="citizen"
        )
        self.moderator = User.objects.create_user(
            email="moderator@delhi.gov.in",
            password="password123",
            name="Officer Sharma",
            role="gov_admin"
        )
        self.coordinator_a = User.objects.create_user(
            email="coordinator@dtu.ac.in",
            password="password123",
            name="Prof. Verma (Coordinator)",
            role="university_coordinator",
            university=self.univ_a
        )
        self.faculty_a = User.objects.create_user(
            email="faculty@dtu.ac.in",
            password="password123",
            name="Dr. Gupta (Faculty)",
            role="faculty_mentor",
            university=self.univ_a
        )
        self.student_a = User.objects.create_user(
            email="student@dtu.ac.in",
            password="password123",
            name="Aarav Student",
            role="student",
            university=self.univ_a
        )
        self.student_b = User.objects.create_user(
            email="student@au.ac.in",
            password="password123",
            name="Kavya Student B",
            role="student",
            university=self.univ_b
        )
        self.industry_rep = User.objects.create_user(
            email="partner@tatapower.com",
            password="password123",
            name="Mr. Tata Rep",
            role="industry_partner"
        )

        # 3. Create a Challenge
        self.issue = Issue.objects.create(
            title="Yamuna River Water Quality Monitoring",
            description="Install IoT telemetry sensors along Wazirabad barrage for BOD and COD monitoring.",
            expected_outcome="Real-time water pollution tracking.",
            district="North West Delhi",
            submitted_by=self.citizen,
            photo_url="https://images.unsplash.com/photo-1544620347-c4fd4a3d5957",
            status=Issue.Status.SUBMITTED
        )

    # -------------------------------------------------------------------------
    # Issue 41: Challenge vs Solution Discussion Separation & Categories
    # -------------------------------------------------------------------------
    def test_issue_41_challenge_discussion_categories_and_filtering(self):
        """Challenge discussions support categories (clarification, requirements, constraints, evidence)."""
        self.client.force_authenticate(user=self.citizen)

        # Post clarification comment
        res1 = self.client.post(f'/api/issues/{self.issue.id}/discussions/', {
            'content': 'Citizen note: Peak pollution occurs during early morning hours between 4 AM and 7 AM.',
            'category': 'clarification'
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data['category'], 'clarification')

        # Post requirements comment
        self.client.force_authenticate(user=self.coordinator_a)
        res2 = self.client.post(f'/api/issues/{self.issue.id}/discussions/', {
            'content': 'Coordinator requirement: Sensors must have IP68 waterproofing and 4G telemetry fallback.',
            'category': 'requirements'
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.data['category'], 'requirements')

        # Filter by clarification
        res_clar = self.client.get(f'/api/issues/{self.issue.id}/discussions/?category=clarification')
        self.assertEqual(res_clar.status_code, status.HTTP_200_OK)
        comments = res_clar.data if isinstance(res_clar.data, list) else res_clar.data.get('results', [])
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]['category'], 'clarification')

        # Filter by requirements
        res_req = self.client.get(f'/api/issues/{self.issue.id}/discussions/?category=requirements')
        self.assertEqual(res_req.status_code, status.HTTP_200_OK)
        comments_req = res_req.data if isinstance(res_req.data, list) else res_req.data.get('results', [])
        self.assertEqual(len(comments_req), 1)
        self.assertEqual(comments_req[0]['category'], 'requirements')

    def test_issue_41_solution_discussion_categories_and_separation(self):
        """Solution discussions are strictly separated from challenge discussions and support technical categories."""
        # Create a Pitch on this Issue
        pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.univ_a,
            title="Solar-powered IoT Sensor Buoys",
            public_summary="Autonomous buoys with optical sensors.",
            confidential_package="Encrypted sensor schematics",
            status=Pitch.Status.SUBMITTED
        )
        pitch.student_team.add(self.student_a)

        self.client.force_authenticate(user=self.faculty_a)
        res1 = self.client.post(f'/api/pitches/{pitch.id}/discussions/', {
            'content': 'Faculty technical review: Consider using LoRaWAN instead of 4G to reduce battery drain.',
            'category': 'technical'
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data['category'], 'technical')

        # Filter solution discussion by category
        res_tech = self.client.get(f'/api/pitches/{pitch.id}/discussions/?category=technical')
        self.assertEqual(res_tech.status_code, status.HTTP_200_OK)
        data = res_tech.data if isinstance(res_tech.data, list) else res_tech.data.get('results', [])
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['category'], 'technical')

        # Verify challenge discussions do NOT leak solution comments
        res_ch = self.client.get(f'/api/issues/{self.issue.id}/discussions/')
        ch_comments = res_ch.data if isinstance(res_ch.data, list) else res_ch.data.get('results', [])
        self.assertEqual(len(ch_comments), 0)

        # Verify solution discussions do NOT leak challenge comments
        res_sol = self.client.get(f'/api/pitches/{pitch.id}/discussions/')
        sol_comments = res_sol.data if isinstance(res_sol.data, list) else res_sol.data.get('results', [])
        self.assertEqual(len(sol_comments), 1)

    # -------------------------------------------------------------------------
    # Issue 42: Authoritative Challenge Ownership Model
    # -------------------------------------------------------------------------
    def test_issue_42_challenge_ownership_model(self):
        """Challenge ownership returns Citizen (created_by), Authority (validated_by), University, and Coordinator."""
        # 1. Initial State: Created by Citizen
        res = self.client.get(f'/api/issues/{self.issue.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ownership = res.data.get('ownership', {})
        self.assertEqual(ownership['created_by']['id'], self.citizen.id)
        self.assertIsNone(ownership['validated_by'])
        self.assertIsNone(ownership['maintaining_university'])
        self.assertIsNone(ownership['managed_by'])

        # 2. Moderation: Validated by Authority
        self.client.force_authenticate(user=self.moderator)
        mod_res = self.client.post(f'/api/issues/{self.issue.id}/moderate/', {
            'action': 'validate',
            'notes': 'Approved for university adoption pipeline'
        }, format='json')
        self.assertEqual(mod_res.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.validated_by, self.moderator)

        # 3. Adoption: Maintained by University, Managed by Coordinator
        self.client.force_authenticate(user=self.coordinator_a)
        adopt_res = self.client.post(f'/api/issues/{self.issue.id}/adopt/', {}, format='json')
        self.assertEqual(adopt_res.status_code, status.HTTP_201_CREATED)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.maintaining_university, self.univ_a)
        self.assertEqual(self.issue.managed_by, self.coordinator_a)

        # 4. Verify Authoritative Ownership Object
        res2 = self.client.get(f'/api/issues/{self.issue.id}/')
        owner2 = res2.data.get('ownership', {})
        self.assertEqual(owner2['created_by']['id'], self.citizen.id)
        self.assertEqual(owner2['validated_by']['id'], self.moderator.id)
        self.assertEqual(owner2['maintaining_university']['id'], self.univ_a.id)
        self.assertEqual(owner2['managed_by']['id'], self.coordinator_a.id)

    def test_issue_42_nomination_approval_syncs_ownership(self):
        """Student nomination approval correctly establishes maintaining university and managing coordinator."""
        self.issue.status = Issue.Status.VALIDATED
        self.issue.validated_by = self.moderator
        self.issue.save()

        # Student nominates
        self.client.force_authenticate(user=self.student_a)
        nom_res = self.client.post(f'/api/issues/{self.issue.id}/nominate/', {
            'rationale': 'DTU Environmental Lab can prototype telemetry sensors.'
        }, format='json')
        self.assertEqual(nom_res.status_code, status.HTTP_201_CREATED)
        nom_id = nom_res.data['id']

        # Coordinator approves
        self.client.force_authenticate(user=self.coordinator_a)
        app_res = self.client.post(f'/api/issues/nominations/{nom_id}/review/', {
            'action': 'approve'
        }, format='json')
        self.assertEqual(app_res.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.maintaining_university, self.univ_a)
        self.assertEqual(self.issue.managed_by, self.coordinator_a)
        self.assertEqual(self.issue.ownership['maintaining_university']['id'], self.univ_a.id)
        self.assertEqual(self.issue.ownership['managed_by']['id'], self.coordinator_a.id)

    # -------------------------------------------------------------------------
    # Issue 43: Challenge Collaborators Model & Role Management
    # -------------------------------------------------------------------------
    def test_issue_43_challenge_collaborators_crud_and_permissions(self):
        """Coordinator can add faculty, students, and industry collaborators to repository."""
        self.issue.status = Issue.Status.ADOPTED
        self.issue.maintaining_university = self.univ_a
        self.issue.managed_by = self.coordinator_a
        self.issue.save()

        # 1. Coordinator adds faculty mentor as collaborator
        self.client.force_authenticate(user=self.coordinator_a)
        res1 = self.client.post(f'/api/issues/{self.issue.id}/collaborators/', {
            'user': self.faculty_a.id,
            'role': ChallengeCollaborator.Role.FACULTY,
            'permissions': {'can_review': True, 'can_co_manage': True}
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data['role'], 'faculty')
        self.assertEqual(res1.data['role_display'], 'Faculty Mentor')
        collab_id = res1.data['id']

        # 2. Coordinator adds student contributor
        res2 = self.client.post(f'/api/issues/{self.issue.id}/collaborators/', {
            'user': self.student_a.id,
            'role': ChallengeCollaborator.Role.STUDENT_CONTRIBUTOR,
            'permissions': {'can_submit_code': True}
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

        # 3. List collaborators
        list_res = self.client.get(f'/api/issues/{self.issue.id}/collaborators/')
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(list_res.data), 2)

        # 4. Remove a collaborator
        del_res = self.client.delete(f'/api/issues/{self.issue.id}/collaborators/{collab_id}/')
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ChallengeCollaborator.objects.filter(id=collab_id).exists())

    def test_issue_43_unauthorized_user_cannot_manage_collaborators(self):
        """Unauthorized student or outside university coordinator cannot add collaborators."""
        self.issue.status = Issue.Status.ADOPTED
        self.issue.maintaining_university = self.univ_a
        self.issue.managed_by = self.coordinator_a
        self.issue.save()

        # Student cannot add collaborator
        self.client.force_authenticate(user=self.student_b)
        res1 = self.client.post(f'/api/issues/{self.issue.id}/collaborators/', {
            'user': self.student_b.id,
            'role': 'student_contributor'
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_403_FORBIDDEN)

    def test_issue_43_collaborator_roles_and_permissions_matrix(self):
        """Collaborator model supports industry_partner and government roles with custom permission dictionaries."""
        self.issue.status = Issue.Status.ADOPTED
        self.issue.maintaining_university = self.univ_a
        self.issue.managed_by = self.coordinator_a
        self.issue.save()

        self.client.force_authenticate(user=self.coordinator_a)
        res = self.client.post(f'/api/issues/{self.issue.id}/collaborators/', {
            'user': self.industry_rep.id,
            'role': ChallengeCollaborator.Role.INDUSTRY_PARTNER,
            'permissions': {'can_sponsor': True, 'csr_funding_available': True}
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['role'], 'industry_partner')
        self.assertEqual(res.data['role_display'], 'Industry Partner')
        self.assertTrue(res.data['permissions']['can_sponsor'])

    # -------------------------------------------------------------------------
    # Issue 44 & 45: Deep-Link / Refresh Safety & Canonical Status Contract
    # -------------------------------------------------------------------------
    def test_issue_44_direct_fetch_details_by_id(self):
        """Detail endpoints return full repository data when fetched directly by :id without frontend memory state."""
        self.client.force_authenticate(user=self.citizen)

        # Fetch issue directly by ID
        res_issue = self.client.get(f'/api/issues/{self.issue.id}/')
        self.assertEqual(res_issue.status_code, status.HTTP_200_OK)
        self.assertEqual(res_issue.data['id'], self.issue.id)
        self.assertEqual(res_issue.data['title'], self.issue.title)

        # Fetch activity timeline directly by ID
        res_act = self.client.get(f'/api/issues/{self.issue.id}/activity/')
        self.assertEqual(res_act.status_code, status.HTTP_200_OK)

        # Fetch status history directly by ID
        res_hist = self.client.get(f'/api/issues/{self.issue.id}/status-history/')
        self.assertEqual(res_hist.status_code, status.HTTP_200_OK)

    def test_issue_45_status_contract_endpoint(self):
        """GET /api/issues/status-contract/ returns authoritative state machine schema for frontend alignment."""
        res = self.client.get('/api/issues/status-contract/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        # Verify challenge statuses and canonical flow
        self.assertIn('challenges', data)
        self.assertIn('submitted', data['challenges']['statuses'])
        self.assertIn('resolved', data['challenges']['statuses'])
        self.assertEqual(data['challenges']['canonical_flow'][0], 'submitted')
        self.assertEqual(data['challenges']['canonical_flow'][-1], 'resolved')

        # Verify solutions statuses and flow
        self.assertIn('solutions', data)
        self.assertIn('submitted', data['solutions']['statuses'])
        self.assertIn('selected', data['solutions']['statuses'])

        # Verify projects statuses and flow
        self.assertIn('projects', data)
        self.assertIn('created', data['projects']['statuses'])
        self.assertIn('verified', data['projects']['statuses'])

        # Verify discussion topics
        self.assertIn('discussion_topics', data)
        self.assertIn('clarification', data['discussion_topics']['challenge'])
        self.assertIn('technical', data['discussion_topics']['solution'])
        self.assertIn('engineering', data['discussion_topics']['project'])

    def test_collaborator_activity_events_logged(self):
        """Adding and removing collaborators logs activity timeline events."""
        self.issue.status = Issue.Status.ADOPTED
        self.issue.maintaining_university = self.univ_a
        self.issue.managed_by = self.coordinator_a
        self.issue.save()

        self.client.force_authenticate(user=self.coordinator_a)
        res = self.client.post(f'/api/issues/{self.issue.id}/collaborators/', {
            'user': self.faculty_a.id,
            'role': ChallengeCollaborator.Role.FACULTY
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        collab_id = res.data['id']

        # Check activity event
        ev_added = ActivityEvent.objects.filter(
            issue=self.issue,
            event_type='COLLABORATOR_ADDED'
        ).first()
        self.assertIsNotNone(ev_added)
        self.assertIn('Dr. Gupta', ev_added.description)

        # Remove collaborator
        self.client.delete(f'/api/issues/{self.issue.id}/collaborators/{collab_id}/')
        ev_removed = ActivityEvent.objects.filter(
            issue=self.issue,
            event_type='COLLABORATOR_REMOVED'
        ).first()
        self.assertIsNotNone(ev_removed)
