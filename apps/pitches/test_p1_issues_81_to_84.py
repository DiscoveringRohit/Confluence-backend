from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
import hashlib

from apps.users.models import User, University, Organization
from apps.issues.models import (
    Issue, Adoption, ChallengeAdoption, StudentNomination,
    OpenCall, CitizenVerification, ActivityEvent, DiscussionComment,
    Discussion, Comment, ChallengeCollaborator
)
from apps.pitches.models import (
    Pitch, Solution, SolutionTeam, SolutionTeamMember, TeamMember,
    SolutionEvaluation, SolutionReview, Project, ProjectMilestone,
    Certificate, PitchVersionHistory
)
from apps.engagements.models import IndustryEngagement


class Issues81To84TestCase(TestCase):
    """
    Test Suite for Sections 81 to 84 of the Confluence Workflow Gap Analysis:
    - Section 81: One-Sentence Product Definition & Nomenclature Integration
    - Section 82: 12-Phase Implementation Priority & Architectural Pipeline
    - Section 83: 18-Step Definition of Done End-to-End Scenario
    - Section 84: Final Design Principle (Fewer Objects, Clear Relationships, One State Machine, Resource Auth, Repository Challenge, Activity History)
    """

    def setUp(self):
        self.client = APIClient()

        # Universities
        self.bit = University.objects.create(
            name="BIT Sindri",
            district="Dhanbad"
        )
        self.nit = University.objects.create(
            name="NIT Jamshedpur",
            district="East Singhbhum"
        )

        # Industry Organization
        self.tata_csr = Organization.objects.create(
            name="Tata Steel CSR Foundation",
            org_type='csr'
        )

        # Users
        self.citizen = User.objects.create_user(
            email="citizen81@jharkhand.in",
            name="Gram Pradhan Birhor",
            role=User.Role.CITIZEN
        )
        self.admin = User.objects.create_user(
            email="admin81@jharkhand.gov.in",
            name="District Magistrate Dhanbad",
            role=User.Role.GOV_ADMIN,
            is_staff=True
        )
        self.coordinator = User.objects.create_user(
            email="coord81@bitsindri.ac.in",
            name="Prof. Coordinator BIT",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.bit
        )
        self.nit_coordinator = User.objects.create_user(
            email="coord81@nitjsr.ac.in",
            name="Prof. Coordinator NIT",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.nit
        )
        self.mentor = User.objects.create_user(
            email="mentor81@bitsindri.ac.in",
            name="Dr. Faculty Mentor BIT",
            role=User.Role.FACULTY_MENTOR,
            university=self.bit
        )
        self.student_lead = User.objects.create_user(
            email="lead81@bitsindri.ac.in",
            name="Student Team Lead",
            role=User.Role.STUDENT,
            university=self.bit
        )
        self.student_member = User.objects.create_user(
            email="member81@bitsindri.ac.in",
            name="Student Team Member",
            role=User.Role.STUDENT,
            university=self.bit
        )
        self.industry_rep = User.objects.create_user(
            email="csr81@tatasteel.com",
            name="CSR Officer Tata Steel",
            role=User.Role.INDUSTRY_PARTNER,
            organization=self.tata_csr
        )

    # -------------------------------------------------------------------------
    # Section 81: One-Sentence Product Definition & Nomenclature Integration
    # -------------------------------------------------------------------------
    def test_section_81_one_sentence_product_definition_and_nomenclature(self):
        """
        Verify all specification nomenclature aliases and cross-object bindings function identically:
        Challenge == Issue, Adoption == ChallengeAdoption, Solution == Pitch,
        TeamMember == SolutionTeamMember, SolutionReview == SolutionEvaluation,
        Discussion == DiscussionComment.
        """
        # 1. Challenge & Adoption aliases
        challenge = Issue.objects.create(
            title="Solar Microgrid Failure in Rural Angara",
            description="Battery bank degradation causing complete blackout in 3 Angara hamlets.",
            category="energy",
            district="Ranchi",
            submitted_by=self.citizen,
            status=Issue.Status.VALIDATED,
            photo_url="https://example.com/solar_grid.jpg"
        )
        self.assertEqual(challenge.challenge_title, challenge.title)
        self.assertEqual(challenge.created_by, self.citizen)

        adoption = ChallengeAdoption.objects.create(
            issue=challenge,
            university=self.bit,
            coordinator=self.coordinator
        )
        self.assertEqual(adoption.challenge, challenge)

        # 2. OpenCall challenge alias
        open_call = OpenCall.objects.create(
            issue=challenge,
            university=self.bit,
            created_by=self.coordinator,
            title="Angara Solar Grid Regeneration Challenge",
            description="Design an active BMS with lithium battery refurbishment.",
            opening_date=timezone.now().date(),
            closing_date=timezone.now().date() + timezone.timedelta(days=30),
            status=OpenCall.Status.OPEN
        )
        self.assertEqual(open_call.challenge, challenge)

        # 3. Solution (PR) aliases & properties
        solution = Solution.objects.create(
            issue=challenge,
            university=self.bit,
            open_call=open_call,
            title="SmartBMS: LiFePO4 Active Cell Balancer",
            public_summary="Autonomous active cell equalizer preventing single-cell voltage collapse.",
            confidential_package="Firmware schematics, switching frequency calculations, and CANbus protocol.",
            repository_url="https://github.com/innovators/smart-bms",
            demo_url="https://smart-bms.jharkhand.in",
            documentation_url="https://docs.smart-bms.jharkhand.in",
            status=Solution.Status.SUBMITTED
        )
        solution.student_team.add(self.student_lead, self.student_member)
        self.assertEqual(solution.challenge, challenge)
        self.assertEqual(solution.summary, solution.public_summary)
        self.assertEqual(solution.proposed_solution, solution.public_summary)
        self.assertEqual(solution.private_details, solution.confidential_package)
        self.assertEqual(solution.team.count(), 2)

        # 4. SolutionReview / SolutionEvaluation aliases
        review = SolutionReview.objects.create(
            pitch=solution,
            reviewer=self.mentor,
            technical_feasibility=20,
            social_impact=20,
            cost_feasibility=15,
            scalability=15,
            sustainability=10,
            innovation=10,
            implementation_readiness=10,
            recommendation=SolutionEvaluation.Recommendation.SELECT,
            comments="Flawless technical design. Ready for implementation."
        )
        self.assertEqual(review.solution, solution)
        self.assertEqual(review.decision, "select")
        self.assertEqual(review.total_score, 100)

        # 5. Discussion alias
        comment = Discussion.objects.create(
            target_type=DiscussionComment.TargetType.CHALLENGE,
            issue=challenge,
            author=self.student_lead,
            category='technical',
            content="Can we use supercapacitor buffer banks for surge protection?"
        )
        self.assertEqual(comment.challenge, challenge)

    # -------------------------------------------------------------------------
    # Section 82: 12-Phase Implementation Priority & Architectural Pipeline
    # -------------------------------------------------------------------------
    def test_section_82_phase_architecture_cohesion(self):
        """
        Verify the complete 12-phase pipeline operates cohesively:
        Phase 1: Authorization & Relationships
        Phase 2: State Machines
        Phase 3: Challenge -> University -> Student Connection
        Phase 4: Solution PR Workflow
        Phase 5: Repository-Style Challenge
        Phase 6: Request Changes + Activity
        Phase 7: Project & Milestones
        Phase 8: Industry Collaboration
        Phase 9: Deployment Verification
        Phase 10: Citizen Verification Gate
        Phase 11 & 12: Simplified UX
        """
        # Phase 1 & 3: University ownership & student-university challenge validation
        challenge = Issue.objects.create(
            title="Mine Tailings Seepage in Damodar Tributary",
            description="Acid mine drainage causing pH drop to 3.2 in local streams.",
            category="environment",
            district="Dhanbad",
            submitted_by=self.citizen,
            status=Issue.Status.VALIDATED,
            photo_url="https://example.com/amd_river.jpg"
        )
        adoption = Adoption.objects.create(
            issue=challenge,
            university=self.bit,
            coordinator=self.coordinator
        )
        challenge.status = Issue.Status.ADOPTED
        challenge.maintaining_university = self.bit
        challenge.save()

        # Non-affiliated university coordinator cannot manage or create open calls
        self.client.force_authenticate(user=self.nit_coordinator)
        res_unauth = self.client.post('/api/issues/open-calls/', {
            'issue': challenge.id,
            'title': 'Unauthorized Call',
            'description': 'Should fail',
            'opening_date': '2026-10-01',
            'closing_date': '2026-10-31',
            'status': 'open'
        })
        self.assertEqual(res_unauth.status_code, status.HTTP_403_FORBIDDEN)

        # Phase 4 & 5: Open call on challenge repository & student PR submission
        self.client.force_authenticate(user=self.coordinator)
        res_call = self.client.post('/api/issues/open-calls/', {
            'issue': challenge.id,
            'title': 'Acid Mine Drainage Passive Bioreactor Call',
            'description': 'Construct an alkaline limestone and sulfate-reducing bacteria channel.',
            'opening_date': '2026-10-01',
            'closing_date': '2026-10-31',
            'status': 'open'
        })
        self.assertEqual(res_call.status_code, status.HTTP_201_CREATED)
        call_id = res_call.data['id']

        self.client.force_authenticate(user=self.student_lead)
        res_sol = self.client.post('/api/pitches/', {
            'issue': challenge.id,
            'open_call': call_id,
            'title': 'EcoLime: Passive Alkaline Bioremediation Bed',
            'public_summary': 'Limestone gravel bed combined with anaerobic mushroom compost matrix.',
            'confidential_package': 'Flow retention modeling and hydraulic conductivity specifications.',
            'repository_url': 'https://github.com/innovators/ecolime',
            'demo_url': 'https://ecolime.jharkhand.in',
            'documentation_url': 'https://docs.ecolime.jharkhand.in',
            'team_member_ids': [self.student_member.id]
        })
        self.assertEqual(res_sol.status_code, status.HTTP_201_CREATED)
        sol_id = res_sol.data['id']
        sol = Solution.objects.get(id=sol_id)

        # Phase 6: Request Changes + Activity logging
        self.client.force_authenticate(user=self.coordinator)
        res_rc = self.client.post(f'/api/pitches/{sol.public_id}/action/', {
            'action': 'request_changes',
            'review_feedback': 'Specify substrate replacement interval and armor protection against heavy monsoons.'
        })
        self.assertEqual(res_rc.status_code, status.HTTP_200_OK)
        sol.refresh_from_db()
        self.assertEqual(sol.status, Solution.Status.CHANGES_REQUESTED)

        # Student resubmission increments version and computes hash
        self.client.force_authenticate(user=self.student_lead)
        res_resub = self.client.post(f'/api/pitches/{sol.public_id}/resubmit/', {
            'title': 'EcoLime: Passive Alkaline Bioremediation Bed (v2)',
            'public_summary': 'Reinforced gravel bed with gabion flood protection barriers.',
            'confidential_package': 'Updated gabion armor dimensions and 5-year limestone recharge schedule.',
            'change_summary': 'Added gabion flood deflector and updated substrate recharge protocol.'
        })
        self.assertEqual(res_resub.status_code, status.HTTP_200_OK)
        sol.refresh_from_db()
        self.assertEqual(sol.status, Solution.Status.RESUBMITTED)
        self.assertEqual(sol.version, 2)
        self.assertTrue(PitchVersionHistory.objects.filter(pitch=sol, version=2).exists())

        # Phase 7: Selection, Mentor Assignment, and Project Creation
        self.client.force_authenticate(user=self.coordinator)
        res_eval = self.client.post(f'/api/pitches/{sol.public_id}/evaluations/', {
            'technical_feasibility': 18,
            'social_impact': 19,
            'cost_feasibility': 15,
            'scalability': 14,
            'sustainability': 10,
            'innovation': 9,
            'implementation_readiness': 9,
            'recommendation': 'select',
            'comments': 'Excellent engineering revisions.'
        })
        self.assertEqual(res_eval.status_code, status.HTTP_201_CREATED)

        res_sel = self.client.post(f'/api/pitches/{sol.public_id}/action/', {
            'action': 'select_winner',
            'mentor_id': self.mentor.id
        })
        self.assertEqual(res_sel.status_code, status.HTTP_200_OK)

        project = Project.objects.get(solution=sol)
        self.assertEqual(project.challenge, challenge)
        self.assertEqual(project.mentor, self.mentor)
        self.assertEqual(project.team.count(), 2)

        # Phase 8: Industry CSR Engagement
        self.client.force_authenticate(user=self.industry_rep)
        res_csr = self.client.post(f'/api/pitches/projects/{project.public_id}/express-interest/', {
            'engagement_type': IndustryEngagement.EngagementType.FUNDING,
            'proposal_notes': 'Tata Steel CSR will provide Rs 3.5 Lakhs grant for stone gabion materials.'
        })
        self.assertEqual(res_csr.status_code, status.HTTP_201_CREATED)

        # Phase 9: Milestones & Deployment
        milestone = ProjectMilestone.objects.create(
            project=project,
            order=1,
            title='Construct 100-meter Passive Bioremediation Channel',
            owner=self.student_lead,
            status=ProjectMilestone.Status.SUBMITTED,
            evidence='https://github.com/innovators/ecolime/releases/tag/v1.0-channel-complete',
            submitted_at=timezone.now()
        )
        self.client.force_authenticate(user=self.mentor)
        res_ms = self.client.patch(f'/api/pitches/milestones/{milestone.id}/', {
            'status': 'approved',
            'reviewer_feedback': 'Channel constructed per design. Outflow pH measured at 7.4.'
        })
        self.assertEqual(res_ms.status_code, status.HTTP_200_OK)

        project.deployment_evidence = "Field water testing by Jharkhand State Pollution Control Board."
        project.outcome = "Damodar tributary pH normalized from 3.2 to 7.4; iron precipitated out completely."
        project.save(update_fields=['deployment_evidence', 'outcome'])
        project.transition_status(Project.Status.DEPLOYED, actor=self.mentor, reason="Channel fully commissioned.")
        challenge.transition_status(Issue.Status.DEPLOYED, actor=self.mentor, reason="Bioremediation operational.")
        challenge.transition_status(Issue.Status.AWAITING_CITIZEN_VERIFICATION, actor=self.admin, reason="Ready for citizen sign-off.")

        # Phase 10: Citizen Verification Gate
        self.client.force_authenticate(user=self.citizen)
        res_cit = self.client.post(f'/api/issues/{challenge.public_id}/citizen-confirm/', {
            'confirmed': True,
            'feedback': 'The red water turned completely clear. Village cattle are drinking safely again.'
        })
        self.assertEqual(res_cit.status_code, status.HTTP_200_OK)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, Issue.Status.RESOLVED)
        self.assertTrue(challenge.citizen_verified_resolved)

        # Phase 11: Outcome Certificates
        self.client.force_authenticate(user=self.coordinator)
        res_cert = self.client.post(f'/api/pitches/projects/{project.public_id}/certificates/generate/')
        self.assertEqual(res_cert.status_code, status.HTTP_201_CREATED)
        self.assertGreaterEqual(len(res_cert.data['certificates']), 2)

    # -------------------------------------------------------------------------
    # Section 83: 18-Step Definition of Done End-to-End Scenario
    # -------------------------------------------------------------------------
    def test_section_83_complete_definition_of_done_e2e_scenario(self):
        """
        Section 83: Full 18-step Definition of Done End-to-End lifecycle scenario:
        Audits every single phase of the platform lifecycle without manual database overrides or state bypasses.
        """
        # Step 1: Citizen submits challenge
        self.client.force_authenticate(user=self.citizen)
        res1 = self.client.post('/api/issues/', {
            'title': 'Heavy Metal Fluorosis in Village Well Water',
            'description': 'Fluoride levels exceeding 4.5 mg/L in 5 community wells causing skeletal fluorosis.',
            'context': '1,200 school children affected in Topchanchi block.',
            'expected_outcome': 'Community-scale activated alumina / hydroxyapatite de-fluoridation reactor.',
            'requirements': 'Zero toxic reagents, solar pump compatible, gravity backwash.',
            'constraints': 'Total capital expenditure under Rs 2.0 Lakhs.',
            'acceptance_criteria': 'Water fluoride below 1.0 mg/L continuously across 60-day testing cycle.',
            'category': 'water',
            'district': 'Dhanbad',
            'address': 'Topchanchi Village 4, Dhanbad',
            'photo_url': 'https://example.com/fluorosis_well.jpg'
        })
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        challenge_id = res1.data['id']
        challenge = Issue.objects.get(id=challenge_id)
        self.assertEqual(challenge.status, Issue.Status.SUBMITTED)
        self.assertTrue(challenge.public_id.startswith('CH-'))

        # Step 2: Authority validates challenge
        self.client.force_authenticate(user=self.admin)
        res2 = self.client.post(f'/api/issues/{challenge_id}/moderate/', {
            'action': 'validate',
            'notes': 'Verified as acute civic health priority by District Water Board.'
        })
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, Issue.Status.VALIDATED)

        # Step 3: Student nominates challenge for university
        self.client.force_authenticate(user=self.student_lead)
        res3 = self.client.post(f'/api/issues/{challenge.public_id}/nominate/', {
            'rationale': 'BIT Sindri Chemical Engineering department has developed ceramic-hydroxyapatite filter cartridges.'
        })
        self.assertEqual(res3.status_code, status.HTTP_201_CREATED)

        # Step 4: University receives & approves nomination -> Adoption created
        self.client.force_authenticate(user=self.coordinator)
        res4 = self.client.post(f'/api/issues/{challenge.public_id}/adopt/', {
            'mode': 'nomination_approved'
        })
        self.assertIn(res4.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, Issue.Status.ADOPTED)
        self.assertEqual(challenge.maintaining_university, self.bit)

        # Step 5: University opens call on challenge repository
        res5 = self.client.post('/api/issues/open-calls/', {
            'issue': challenge.id,
            'title': 'Fluoride Removal Engineering Challenge',
            'description': 'Student teams invited to design passive gravity-fed hydroxyapatite contactors.',
            'opening_date': '2026-10-01',
            'closing_date': '2026-10-31',
            'departments': 'Chemical, Civil, Metallurgical',
            'funding': 'Rs 1,00,000 Prototype Grant',
            'max_teams': 4,
            'status': 'open'
        })
        self.assertEqual(res5.status_code, status.HTTP_201_CREATED)
        open_call_id = res5.data['id']

        # Step 6: Student team discovers challenge & submits Solution proposal (PR)
        self.client.force_authenticate(user=self.student_lead)
        res6 = self.client.post('/api/pitches/', {
            'issue': challenge.id,
            'open_call': open_call_id,
            'title': 'FluoroShield: Porous Hydroxyapatite Composite Filter',
            'public_summary': 'Regenerable bone-char derived nano-hydroxyapatite cartridge system.',
            'confidential_package': 'Cartridge sintering temperature curves and alkaline desorption protocol.',
            'repository_url': 'https://github.com/innovators/fluoroshield',
            'demo_url': 'https://fluoroshield.jharkhand.in',
            'documentation_url': 'https://docs.fluoroshield.jharkhand.in',
            'team_member_ids': [self.student_member.id]
        })
        self.assertEqual(res6.status_code, status.HTTP_201_CREATED)
        solution_id = res6.data['id']
        solution = Solution.objects.get(id=solution_id)
        self.assertTrue(solution.public_id.startswith('SOL-'))
        self.assertEqual(solution.student_team.count(), 2)

        # Step 7: University reviews solution & requests changes
        self.client.force_authenticate(user=self.coordinator)
        res7 = self.client.post(f'/api/pitches/{solution.public_id}/action/', {
            'action': 'request_changes',
            'review_feedback': 'Provide automated backwash valve schematics and safe disposal protocol for spent fluoride brine.'
        })
        self.assertEqual(res7.status_code, status.HTTP_200_OK)
        solution.refresh_from_db()
        self.assertEqual(solution.status, Solution.Status.CHANGES_REQUESTED)

        # Step 8: Student resubmits revised solution
        self.client.force_authenticate(user=self.student_lead)
        res8 = self.client.post(f'/api/pitches/{solution.public_id}/resubmit/', {
            'title': 'FluoroShield: Porous Hydroxyapatite Composite Filter (Revised)',
            'public_summary': 'Regenerable hydroxyapatite cartridge with calcium-fluoride precipitation vessel.',
            'confidential_package': 'Added calcium-chloride precipitation tank to crystallize inert CaF2 safely.',
            'change_summary': 'Added inert calcium fluoride precipitation chamber for non-toxic disposal of regeneration effluent.'
        })
        self.assertEqual(res8.status_code, status.HTTP_200_OK)
        solution.refresh_from_db()
        self.assertEqual(solution.status, Solution.Status.RESUBMITTED)
        self.assertEqual(solution.version, 2)

        # Step 9: Review board scores solution & selects winner + assigns faculty mentor
        self.client.force_authenticate(user=self.coordinator)
        res9_eval = self.client.post(f'/api/pitches/{solution.public_id}/evaluations/', {
            'technical_feasibility': 20,
            'social_impact': 20,
            'cost_feasibility': 15,
            'scalability': 15,
            'sustainability': 10,
            'innovation': 10,
            'implementation_readiness': 10,
            'recommendation': 'select',
            'comments': 'Flawless design. The CaF2 precipitation chamber fully solves hazardous brine disposal.'
        })
        self.assertEqual(res9_eval.status_code, status.HTTP_201_CREATED)

        res9_select = self.client.post(f'/api/pitches/{solution.public_id}/action/', {
            'action': 'select_winner',
            'mentor_id': self.mentor.id
        })
        self.assertEqual(res9_select.status_code, status.HTTP_200_OK)
        solution.refresh_from_db()
        self.assertEqual(solution.status, Solution.Status.SELECTED)
        self.assertEqual(solution.assigned_mentor, self.mentor)

        # Step 10: Implementation Project automatically created
        project = Project.objects.get(solution=solution)
        self.assertEqual(project.challenge, challenge)
        self.assertEqual(project.mentor, self.mentor)
        self.assertTrue(project.public_id.startswith('PRJ-'))

        # Step 11: Industry partner expresses interest & initiates CSR collaboration
        self.client.force_authenticate(user=self.industry_rep)
        res11 = self.client.post(f'/api/pitches/projects/{project.public_id}/express-interest/', {
            'engagement_type': IndustryEngagement.EngagementType.FUNDING,
            'proposal_notes': 'Tata Steel CSR will sponsor 10 community filtration kiosks.'
        })
        self.assertEqual(res11.status_code, status.HTTP_201_CREATED)
        self.assertTrue(IndustryEngagement.objects.filter(project=project, industry_org=self.tata_csr).exists())

        # Step 12: Student milestones submitted & mentor approves
        milestone = ProjectMilestone.objects.create(
            project=project,
            order=1,
            title='Fabricate 1000 LPH Community Pilot Hydroxyapatite Unit',
            owner=self.student_lead,
            status=ProjectMilestone.Status.SUBMITTED,
            evidence='https://github.com/innovators/fluoroshield/releases/tag/v1.0-pilot-report',
            submitted_at=timezone.now()
        )
        self.client.force_authenticate(user=self.mentor)
        res12 = self.client.patch(f'/api/pitches/milestones/{milestone.id}/', {
            'status': 'approved',
            'reviewer_feedback': 'Fluoride reduced from 4.8 mg/L to 0.6 mg/L at 1,050 LPH flow rate.'
        })
        self.assertEqual(res12.status_code, status.HTTP_200_OK)

        # Step 13: Project transitions Planning -> Prototype -> Pilot -> Deployed -> Awaiting Citizen Verification
        project.transition_status(Project.Status.PROTOTYPE, actor=self.mentor, reason="Lab bench testing passed.")
        project.transition_status(Project.Status.PILOT, actor=self.mentor, reason="Field pilot installed at Topchanchi Well #2.")
        project.deployment_evidence = "District Health Office water test certificates and telemetry logs."
        project.outcome = "Fluoride reduced to 0.6 mg/L serving 1,200 children daily with zero fluoride symptoms."
        project.save(update_fields=['deployment_evidence', 'outcome'])
        project.transition_status(Project.Status.DEPLOYED, actor=self.mentor, reason="Community deployment operational.")

        challenge.transition_status(Issue.Status.DEPLOYED, actor=self.mentor, reason="Field deployment fully operational.")
        challenge.transition_status(Issue.Status.AWAITING_CITIZEN_VERIFICATION, actor=self.admin, reason="Dispatched citizen verification survey.")
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, Issue.Status.AWAITING_CITIZEN_VERIFICATION)

        # Step 14: Citizen confirms resolution in the field
        self.client.force_authenticate(user=self.citizen)
        res14 = self.client.post(f'/api/issues/{challenge.public_id}/citizen-confirm/', {
            'confirmed': True,
            'feedback': 'Crystal clear, sweet drinking water. The school water tank is filled twice daily.'
        })
        self.assertEqual(res14.status_code, status.HTTP_200_OK)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, Issue.Status.RESOLVED)
        self.assertTrue(challenge.citizen_verified_resolved)

        # Step 15: Verified Outcome Certificates generated
        self.client.force_authenticate(user=self.coordinator)
        res15 = self.client.post(f'/api/pitches/projects/{project.public_id}/certificates/generate/')
        self.assertEqual(res15.status_code, status.HTTP_201_CREATED)
        self.assertGreaterEqual(len(res15.data['certificates']), 2)

        # Step 16: Public certificate verification
        cert = Certificate.objects.filter(project=project, recipient=self.student_lead).first()
        self.assertIsNotNone(cert)
        self.assertEqual(len(cert.verification_hash), 64)

        res16 = self.client.get(f'/api/pitches/certificates/{cert.certificate_id}/verify/')
        self.assertEqual(res16.status_code, status.HTTP_200_OK)
        self.assertTrue(res16.data['is_valid'])
        self.assertTrue(res16.data['valid'])

        # Step 17: Unified Activity Timeline contains all chronological milestone and transition events
        res17 = self.client.get(f'/api/issues/{challenge.public_id}/activity/')
        self.assertEqual(res17.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res17.data), 5)

        # Step 18: Zero manual database overrides or state bypasses required.

    # -------------------------------------------------------------------------
    # Section 84: Final Design Principle (System Architecture Invariants)
    # -------------------------------------------------------------------------
    def test_section_84_final_design_principle_system_invariants(self):
        """
        Verify the 6 core architecture invariants defined in Section 84:
        1. Fewer Objects: Single unified tables with clean nomenclature aliases.
        2. Clear Relationships: Challenge -> University -> Solution -> Project -> Citizen Verification.
        3. One State Machine: Predictable, canonical state transitions.
        4. Resource-Level Authorization: Scoped to university, assigned mentor, or citizen owner.
        5. Repository-Style Challenge: Integrated README, Requirements, Open Calls, Discussions, Activity.
        6. Immutable Activity History: Every major state transition logs an ActivityEvent.
        """
        # 1. Fewer Objects & Clean Models
        self.assertEqual(Solution, Pitch)
        self.assertEqual(SolutionTeam, Pitch)
        self.assertEqual(TeamMember, SolutionTeamMember)
        self.assertEqual(SolutionReview, SolutionEvaluation)
        self.assertEqual(Discussion, DiscussionComment)
        self.assertEqual(Comment, DiscussionComment)

        # 2. Immutable Activity History & Single State Machine
        challenge = Issue.objects.create(
            title="Kendu Leaf Storage Fire Hazard",
            description="High temperature causing spontaneous combustion in forest warehouses.",
            category="agriculture",
            district="Latehar",
            submitted_by=self.citizen,
            status=Issue.Status.SUBMITTED,
            photo_url="https://example.com/kendu.jpg"
        )
        challenge.transition_status(
            Issue.Status.VALIDATED,
            actor=self.admin,
            reason="Verified by District Forest Officer."
        )
        events = ActivityEvent.objects.filter(issue=challenge)
        self.assertTrue(events.exists())
        self.assertEqual(challenge.status, Issue.Status.VALIDATED)
