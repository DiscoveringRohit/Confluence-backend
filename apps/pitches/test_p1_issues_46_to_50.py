from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.issues.models import (
    Issue, Adoption, ChallengeCollaborator
)
from apps.pitches.models import Pitch, Project
from apps.engagements.models import IndustryEngagement
from apps.users.models import University, Organization

User = get_user_model()


class Issues46To50TestCase(TestCase):
    """
    Test suite for Issues 46 to 50 from Confluence Workflow Gap Analysis:
    - Issue 46: Granular API Authorization Model (Resource ownership & role boundaries)
    - Issue 47: Issue Update Authorization & Status Tampering Prevention
    - Issue 48: Scoped University User Directory Endpoints & Auth Gate
    - Issue 49: Strict Industry Engagement Participant Authorization
    - Issue 50: Industry-to-Project Connection & Collaborator Registration
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Setup Universities & Organizations
        self.univ_dtu = University.objects.create(
            name="Delhi Technological University",
            code="DTU",
            district="North West Delhi"
        )
        self.univ_anna = University.objects.create(
            name="Anna University",
            code="AU",
            district="Chennai"
        )
        self.org_tata = Organization.objects.create(
            name="Tata Motors Cleantech",
            website="https://tatamotors.com",
            org_type="industry"
        )
        self.org_infosys = Organization.objects.create(
            name="Infosys Springboard",
            website="https://infosys.com",
            org_type="industry"
        )

        # 2. Setup Users
        self.citizen_1 = User.objects.create_user(
            email="citizen1@delhi.gov.in",
            password="password123",
            name="Ramesh Sharma",
            role="citizen"
        )
        self.citizen_2 = User.objects.create_user(
            email="citizen2@delhi.gov.in",
            password="password123",
            name="Sita Devi",
            role="citizen"
        )
        self.student_dtu = User.objects.create_user(
            email="student@dtu.ac.in",
            password="password123",
            name="Aman Gupta",
            role="student",
            university=self.univ_dtu
        )
        self.student_anna = User.objects.create_user(
            email="student@anna.ac.in",
            password="password123",
            name="Priya Raman",
            role="student",
            university=self.univ_anna
        )
        self.mentor_dtu = User.objects.create_user(
            email="mentor@dtu.ac.in",
            password="password123",
            name="Dr. Rajesh Rao",
            role="faculty_mentor",
            university=self.univ_dtu
        )
        self.coordinator_dtu = User.objects.create_user(
            email="coord@dtu.ac.in",
            password="password123",
            name="Prof. Verma",
            role="university_coordinator",
            university=self.univ_dtu
        )
        self.coordinator_anna = User.objects.create_user(
            email="coord@anna.ac.in",
            password="password123",
            name="Prof. Sundaram",
            role="university_coordinator",
            university=self.univ_anna
        )
        self.industry_tata = User.objects.create_user(
            email="partner@tata.com",
            password="password123",
            name="Tata Lead",
            role="industry_partner",
            organization=self.org_tata
        )
        self.industry_infosys = User.objects.create_user(
            email="partner@infosys.com",
            password="password123",
            name="Infosys Lead",
            role="industry_partner",
            organization=self.org_infosys
        )
        self.gov_admin = User.objects.create_user(
            email="admin@delhi.gov.in",
            password="password123",
            name="Director Delhi Gov",
            role="gov_admin",
            is_staff=True
        )

        # 3. Setup Issues
        self.issue_1 = Issue.objects.create(
            title="Severe Waterlogging at Peeragarhi Flyover",
            description="Monsoon waterlogging blocks emergency lanes daily.",
            submitted_by=self.citizen_1,
            district="North West Delhi",
            category="INFRASTRUCTURE",
            status=Issue.Status.SUBMITTED
        )
        self.issue_adopted = Issue.objects.create(
            title="Solar Microgrid Failure in Badarpur",
            description="Inverter grid synchronization trips frequently.",
            submitted_by=self.citizen_1,
            district="South Delhi",
            category="ENERGY",
            status=Issue.Status.ADOPTED,
            maintaining_university=self.univ_dtu
        )
        self.adoption = Adoption.objects.create(
            issue=self.issue_adopted,
            university=self.univ_dtu,
            coordinator=self.coordinator_dtu,
            status=Adoption.Status.APPROVED
        )

        # 4. Setup Solution & Project
        self.pitch = Pitch.objects.create(
            issue=self.issue_adopted,
            university=self.univ_dtu,
            title="Microgrid Dual Inverter Sync Firmware",
            public_summary="Custom firmware prevents tripping.",
            confidential_package="Proprietary PLL synchronization algorithms and schematic designs.",
            status=Pitch.Status.SELECTED
        )
        self.pitch.student_team.add(self.student_dtu)

        self.project = Project.objects.create(
            solution=self.pitch,
            challenge=self.issue_adopted,
            university=self.univ_dtu,
            mentor=self.mentor_dtu,
            title="Badarpur Solar Microgrid Modernization",
            status=Project.Status.PROTOTYPE
        )
        self.project.team.add(self.student_dtu)

    # -------------------------------------------------------------------------
    # Issue 46: API Authorization Model
    # -------------------------------------------------------------------------
    def test_issue_46_citizen_ownership_authorization(self):
        """Citizen can view and edit their own challenge; cannot update another citizen's challenge (403)."""
        self.client.force_authenticate(user=self.citizen_1)
        # Edit own challenge in SUBMITTED status -> 200
        res = self.client.patch(f'/api/issues/{self.issue_1.id}/', {
            'title': 'Severe Waterlogging at Peeragarhi Flyover - Updated by Citizen'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.issue_1.refresh_from_db()
        self.assertEqual(self.issue_1.title, 'Severe Waterlogging at Peeragarhi Flyover - Updated by Citizen')

        # Attempt to edit citizen_1's challenge as citizen_2 -> 403 Forbidden
        self.client.force_authenticate(user=self.citizen_2)
        res_forbidden = self.client.patch(f'/api/issues/{self.issue_1.id}/', {
            'title': 'Tampered by Citizen 2'
        })
        self.assertEqual(res_forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_issue_46_coordinator_domain_authorization(self):
        """Coordinator can manage challenges adopted by their university, but 403 on challenges adopted by another university."""
        # Coordinator of DTU (adopting university) can update metadata
        self.client.force_authenticate(user=self.coordinator_dtu)
        res_dtu = self.client.patch(f'/api/issues/{self.issue_adopted.id}/', {
            'description': 'Updated operational description by DTU coordinator.'
        })
        self.assertEqual(res_dtu.status_code, status.HTTP_200_OK)

        # Coordinator of Anna University (unrelated university) cannot update DTU's adopted challenge
        self.client.force_authenticate(user=self.coordinator_anna)
        res_anna = self.client.patch(f'/api/issues/{self.issue_adopted.id}/', {
            'description': 'Tampered by Anna University coordinator.'
        })
        self.assertEqual(res_anna.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # Issue 47: Issue Update Authorization & Status Tampering Prevention
    # -------------------------------------------------------------------------
    def test_issue_47_status_tampering_blocked_on_generic_update(self):
        """PUT/PATCH requests cannot bypass state machines to directly alter issue status."""
        self.client.force_authenticate(user=self.citizen_1)
        # Attempt to force issue_1 from SUBMITTED directly to RESOLVED
        res = self.client.patch(f'/api/issues/{self.issue_1.id}/', {
            'status': Issue.Status.RESOLVED,
            'title': 'Attempting Status Jump'
        })
        self.assertIn(res.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        self.issue_1.refresh_from_db()
        # Status must remain SUBMITTED; direct tampering stripped or rejected
        self.assertEqual(self.issue_1.status, Issue.Status.SUBMITTED)

    def test_issue_47_citizen_can_only_edit_in_submitted_or_reopened(self):
        """Citizens can edit their challenge only in SUBMITTED or REOPENED state; 403 in ADOPTED state."""
        self.client.force_authenticate(user=self.citizen_1)
        # Attempt to edit issue_adopted (which is in ADOPTED status)
        res = self.client.patch(f'/api/issues/{self.issue_adopted.id}/', {
            'title': 'Citizen trying to modify adopted challenge'
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Set status to REOPENED -> citizen can edit again
        self.issue_adopted.status = Issue.Status.REOPENED
        self.issue_adopted.save()
        res_reopened = self.client.patch(f'/api/issues/{self.issue_adopted.id}/', {
            'title': 'Citizen modifying reopened challenge'
        })
        self.assertEqual(res_reopened.status_code, status.HTTP_200_OK)
        self.issue_adopted.refresh_from_db()
        self.assertEqual(self.issue_adopted.title, 'Citizen modifying reopened challenge')

    def test_issue_47_coordinator_metadata_update(self):
        """Adopting coordinator can update metadata while maintaining university association."""
        self.client.force_authenticate(user=self.coordinator_dtu)
        res = self.client.patch(f'/api/issues/{self.issue_adopted.id}/', {
            'description': 'Refined technical challenge requirements by coordinator.'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.issue_adopted.refresh_from_db()
        self.assertEqual(self.issue_adopted.description, 'Refined technical challenge requirements by coordinator.')

    # -------------------------------------------------------------------------
    # Issue 48: User Directory & Auth Gate
    # -------------------------------------------------------------------------
    def test_issue_48_user_list_requires_authentication(self):
        """Unauthenticated requests to /api/users/ are rejected with 401 Unauthorized."""
        res = self.client.get('/api/users/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticated user can access directory
        self.client.force_authenticate(user=self.student_dtu)
        res_auth = self.client.get('/api/users/')
        self.assertEqual(res_auth.status_code, status.HTTP_200_OK)

    def test_issue_48_scoped_university_directory_endpoints(self):
        """Scoped endpoints return only students, mentors, or coordinators of the requested university."""
        self.client.force_authenticate(user=self.coordinator_dtu)

        # 1. Students endpoint for DTU
        res_students = self.client.get(f'/api/users/universities/{self.univ_dtu.id}/students/')
        self.assertEqual(res_students.status_code, status.HTTP_200_OK)
        student_data = res_students.data.get('results', res_students.data) if isinstance(res_students.data, dict) else res_students.data
        student_emails = [u['email'] for u in student_data]
        self.assertIn(self.student_dtu.email, student_emails)
        self.assertNotIn(self.student_anna.email, student_emails)

        # 2. Mentors endpoint for DTU
        res_mentors = self.client.get(f'/api/users/universities/{self.univ_dtu.id}/mentors/')
        self.assertEqual(res_mentors.status_code, status.HTTP_200_OK)
        mentor_data = res_mentors.data.get('results', res_mentors.data) if isinstance(res_mentors.data, dict) else res_mentors.data
        mentor_emails = [u['email'] for u in mentor_data]
        self.assertIn(self.mentor_dtu.email, mentor_emails)

        # 3. Coordinators endpoint for DTU
        res_coords = self.client.get(f'/api/users/universities/{self.univ_dtu.id}/coordinators/')
        self.assertEqual(res_coords.status_code, status.HTTP_200_OK)
        coord_data = res_coords.data.get('results', res_coords.data) if isinstance(res_coords.data, dict) else res_coords.data
        coord_emails = [u['email'] for u in coord_data]
        self.assertIn(self.coordinator_dtu.email, coord_emails)
        self.assertNotIn(self.coordinator_anna.email, coord_emails)

    # -------------------------------------------------------------------------
    # Issue 49: Industry Engagement Participant Ownership
    # -------------------------------------------------------------------------
    def test_issue_49_industry_engagement_participant_ownership_enforcement(self):
        """RespondEngagementView enforces strict participant checks (403 for unauthorized users)."""
        # Industry user initiates engagement for adopted issue
        self.client.force_authenticate(user=self.industry_tata)
        create_res = self.client.post('/api/engagements/', {
            'issue': self.issue_adopted.id,
            'engagement_type': IndustryEngagement.EngagementType.PROTOTYPING,
            'proposal_notes': 'Offering EV testbench lab equipment.'
        })
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        engagement_id = create_res.data['id']

        # Random user (citizen or anna coordinator) cannot accept -> 403
        self.client.force_authenticate(user=self.coordinator_anna)
        unauth_res = self.client.post(f'/api/engagements/{engagement_id}/respond/', {
            'action': 'accept',
            'response_notes': 'Anna University trying to accept DTU partnership'
        })
        self.assertEqual(unauth_res.status_code, status.HTTP_403_FORBIDDEN)

        # Authorized DTU coordinator accepts -> 200 OK
        self.client.force_authenticate(user=self.coordinator_dtu)
        accept_res = self.client.post(f'/api/engagements/{engagement_id}/respond/', {
            'action': 'accept',
            'response_notes': 'DTU approves EV testbench access.'
        })
        self.assertEqual(accept_res.status_code, status.HTTP_200_OK)
        self.assertEqual(accept_res.data['status'], IndustryEngagement.Status.ACCEPTED)

    # -------------------------------------------------------------------------
    # Issue 50: Industry-to-Project Connection & Collaborator Registration
    # -------------------------------------------------------------------------
    def test_issue_50_industry_engagement_project_link(self):
        """Industry engagements link directly to the active project and serialize project details."""
        self.client.force_authenticate(user=self.industry_tata)
        res = self.client.post('/api/engagements/', {
            'issue': self.issue_adopted.id,
            'engagement_type': IndustryEngagement.EngagementType.FUNDING,
            'proposal_notes': 'CSR grant funding for microgrid deployment.'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['project'], self.project.id)
        self.assertEqual(res.data['project_title'], self.project.title)

        engagement = IndustryEngagement.objects.get(id=res.data['id'])
        self.assertEqual(engagement.project, self.project)

    def test_issue_50_accept_engagement_auto_registers_challenge_collaborator(self):
        """Accepting an engagement registers the industry partner in ChallengeCollaborator with role 'industry_partner'."""
        self.client.force_authenticate(user=self.industry_tata)
        create_res = self.client.post('/api/engagements/', {
            'issue': self.issue_adopted.id,
            'engagement_type': IndustryEngagement.EngagementType.MENTORSHIP,
            'proposal_notes': 'Providing industry mentorship for inverter firmware.'
        })
        engagement_id = create_res.data['id']

        # Confirm industry_tata is not yet a collaborator
        self.assertFalse(
            ChallengeCollaborator.objects.filter(
                issue=self.issue_adopted,
                user=self.industry_tata
            ).exists()
        )

        # DTU Coordinator accepts engagement
        self.client.force_authenticate(user=self.coordinator_dtu)
        accept_res = self.client.post(f'/api/engagements/{engagement_id}/respond/', {
            'action': 'accept',
            'response_notes': 'Welcome Tata Motors as innovation partner.'
        })
        self.assertEqual(accept_res.status_code, status.HTTP_200_OK)

        # Check ChallengeCollaborator: industry_tata should now be auto-registered
        collab = ChallengeCollaborator.objects.filter(
            issue=self.issue_adopted,
            user=self.industry_tata
        ).first()
        self.assertIsNotNone(collab)
        self.assertEqual(collab.role, ChallengeCollaborator.Role.INDUSTRY_PARTNER)
        self.assertTrue(collab.permissions.get('can_review'))
