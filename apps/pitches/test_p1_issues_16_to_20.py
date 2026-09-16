from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.users.models import User, University
from apps.issues.models import Issue, Adoption, DiscussionComment, ActivityEvent
from apps.pitches.models import (
    Pitch, PitchVersionHistory, SolutionEvaluation, SolutionTeamMember
)


class P1Issues16To20TestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Universities
        self.uni_a = University.objects.create(name="BIT Sindri", district="Dhanbad")
        self.uni_b = University.objects.create(name="Ranchi University", district="Ranchi")

        # Users
        self.citizen = User.objects.create_user(
            email="citizen@jharkhand.in",
            name="Citizen Ramesh",
            role=User.Role.CITIZEN
        )
        self.coord_a = User.objects.create_user(
            email="coord@bitsindri.ac.in",
            name="Coordinator BIT",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_a
        )
        self.coord_b = User.objects.create_user(
            email="coord@ranchi.ac.in",
            name="Coordinator RU",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_b
        )
        self.mentor_a = User.objects.create_user(
            email="mentor@bitsindri.ac.in",
            name="Prof Sharma",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni_a
        )
        self.student_lead = User.objects.create_user(
            email="lead@bitsindri.ac.in",
            name="Student Lead",
            role=User.Role.STUDENT,
            university=self.uni_a
        )
        self.student_dev = User.objects.create_user(
            email="dev@bitsindri.ac.in",
            name="Student Developer",
            role=User.Role.STUDENT,
            university=self.uni_a
        )
        self.student_other_uni = User.objects.create_user(
            email="other@ranchi.ac.in",
            name="Other Student",
            role=User.Role.STUDENT,
            university=self.uni_b
        )

        # Adopted issue
        self.issue = Issue.objects.create(
            title="Arsenic Removal in Damodar Basin",
            description="Groundwater arsenic levels exceed 50 ppb in 6 villages.",
            expected_outcome="Community water filtration units with < 10 ppb arsenic.",
            acceptance_criteria="Continuous flow >= 500 L/hr, replacement cartridge cost < Rs 2000, citizen telemetry enabled.",
            category="water_sanitation",
            district="Dhanbad",
            address="Sindri Ward 2",
            submitted_by=self.citizen,
            status=Issue.Status.ADOPTED
        )
        self.adoption = Adoption.objects.create(
            issue=self.issue,
            university=self.uni_a,
            coordinator=self.coord_a
        )

    # =========================================================================
    # Issue 16 & 17: Solution-as-PR & GitHub/Demo/Documentation Fields
    # =========================================================================

    def test_submit_solution_with_repository_and_demo_links(self):
        """Student submits solution with GitHub repo, live demo, and doc links; history snapshot captures them."""
        self.client.force_authenticate(user=self.student_lead)
        url = "/api/pitches/"
        data = {
            "issue": self.issue.id,
            "title": "Nano-Iron Graphene Arsenic Filter",
            "public_summary": "Low-cost nanoscale iron composite for rapid arsenic adsorption.",
            "confidential_package": "Adsorption kinetics data, cartridge packing geometry, and flow calculations.",
            "repository_url": "https://github.com/bitsindri-water/nano-arsenic-filter",
            "demo_url": "https://demo.arsenicfilter.jharkhand.org",
            "documentation_url": "https://docs.arsenicfilter.jharkhand.org/architecture.pdf",
            "video_url": "https://youtube.com/watch?v=samplevideo",
            "team_member_ids": [self.student_dev.id]
        }
        res = self.client.post(url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        pitch_id = res.data['id']
        pitch = Pitch.objects.get(pk=pitch_id)
        self.assertEqual(pitch.repository_url, data['repository_url'])
        self.assertEqual(pitch.demo_url, data['demo_url'])
        self.assertEqual(pitch.documentation_url, data['documentation_url'])
        self.assertEqual(pitch.video_url, data['video_url'])

        # Verify initial PitchVersionHistory captures URLs
        v1 = pitch.version_history.get(version=1)
        self.assertEqual(v1.repository_url, data['repository_url'])
        self.assertEqual(v1.demo_url, data['demo_url'])
        self.assertEqual(v1.documentation_url, data['documentation_url'])
        self.assertEqual(v1.video_url, data['video_url'])

        # Verify automatic team role registration (Section 22 & P1 Issue 20)
        self.assertEqual(SolutionTeamMember.objects.filter(pitch=pitch).count(), 2)
        lead_member = SolutionTeamMember.objects.get(pitch=pitch, student=self.student_lead)
        dev_member = SolutionTeamMember.objects.get(pitch=pitch, student=self.student_dev)
        self.assertEqual(lead_member.role, SolutionTeamMember.Role.OWNER)
        self.assertEqual(dev_member.role, SolutionTeamMember.Role.DEVELOPER)

    # =========================================================================
    # Issue 18: Solution States & UNDER_REVIEW Transition
    # =========================================================================

    def test_review_board_start_review_action(self):
        """Coordinator starts review of a submitted solution, transitioning status to UNDER_REVIEW."""
        pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.uni_a,
            title="Solar Electro-Filter",
            public_summary="Solar-powered electrolysis filter.",
            confidential_package="Electrode chemistry specs.",
            status=Pitch.Status.SUBMITTED
        )
        pitch.student_team.add(self.student_lead)

        self.client.force_authenticate(user=self.coord_a)
        url = f"/api/pitches/{pitch.id}/review-action/"
        res = self.client.post(url, {"action": "start_review"}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        pitch.refresh_from_db()
        self.assertEqual(pitch.status, Pitch.Status.UNDER_REVIEW)

    def test_evaluating_solution_auto_transitions_to_under_review(self):
        """When an authorized reviewer submits an evaluation, solution automatically transitions to UNDER_REVIEW."""
        pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.uni_a,
            title="Bio-Purifier",
            public_summary="Biological filtration method.",
            confidential_package="Seed enzyme extracts.",
            status=Pitch.Status.SUBMITTED
        )
        pitch.student_team.add(self.student_lead)

        self.client.force_authenticate(user=self.coord_a)
        url = f"/api/pitches/{pitch.id}/evaluations/"
        data = {
            "technical_feasibility": 16,
            "social_impact": 18,
            "cost_feasibility": 12,
            "scalability": 12,
            "sustainability": 8,
            "innovation": 7,
            "implementation_readiness": 7,
            "recommendation": "request_changes",
            "comments": "Promising biological approach; please clarify temperature stability."
        }
        res = self.client.post(url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        pitch.refresh_from_db()
        self.assertEqual(pitch.status, Pitch.Status.UNDER_REVIEW)

    # =========================================================================
    # Issue 19: Request Changes & Resubmission with Links & History
    # =========================================================================

    def test_resubmit_solution_updates_links_and_creates_v2_history(self):
        """Student resubmits solution with updated repo/demo links and receives new version snapshot."""
        pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.uni_a,
            title="Nano Filter v1",
            public_summary="Initial filter summary.",
            confidential_package="Old confidential specs.",
            repository_url="https://github.com/old/repo",
            status=Pitch.Status.CHANGES_REQUESTED,
            version=1
        )
        pitch.student_team.add(self.student_lead)
        PitchVersionHistory.objects.create(
            pitch=pitch,
            version=1,
            title=pitch.title,
            public_summary=pitch.public_summary,
            confidential_package=pitch.confidential_package,
            repository_url=pitch.repository_url,
            change_summary="Initial submission",
            actor=self.student_lead
        )

        self.client.force_authenticate(user=self.student_lead)
        url = f"/api/pitches/{pitch.id}/resubmit/"
        resubmit_data = {
            "title": "Nano Filter v2 (Optimized)",
            "public_summary": "Revised filter summary with field pilot data.",
            "confidential_package": "Revised confidential specifications with corrosion-resistant coating.",
            "repository_url": "https://github.com/bitsindri-water/nano-filter-v2",
            "demo_url": "https://v2.demo.filter.org",
            "change_summary": "Added anti-corrosion coating and updated firmware repo link."
        }
        res = self.client.post(url, resubmit_data, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        pitch.refresh_from_db()
        self.assertEqual(pitch.version, 2)
        self.assertEqual(pitch.status, Pitch.Status.RESUBMITTED)
        self.assertEqual(pitch.repository_url, resubmit_data["repository_url"])
        self.assertEqual(pitch.demo_url, resubmit_data["demo_url"])

        # History has 2 versions
        self.assertEqual(pitch.version_history.count(), 2)
        v2 = pitch.version_history.get(version=2)
        self.assertEqual(v2.title, "Nano Filter v2 (Optimized)")
        self.assertEqual(v2.repository_url, resubmit_data["repository_url"])
        self.assertEqual(v2.demo_url, resubmit_data["demo_url"])
        self.assertEqual(v2.change_summary, resubmit_data["change_summary"])

    # =========================================================================
    # Issue 20: Real Team Model & Collaborator Management
    # =========================================================================

    def test_collaborator_management_and_authorization(self):
        """Lead student can manage collaborator roles; students from other universities rejected."""
        pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.uni_a,
            title="Solar Desalination",
            public_summary="Solar desalination unit.",
            confidential_package="Thermal coil specs.",
            status=Pitch.Status.SUBMITTED
        )
        pitch.student_team.add(self.student_lead)
        SolutionTeamMember.objects.create(
            pitch=pitch,
            student=self.student_lead,
            role=SolutionTeamMember.Role.OWNER
        )

        self.client.force_authenticate(user=self.student_lead)
        url = f"/api/pitches/{pitch.id}/team/"

        # 1. Query team
        res_list = self.client.get(url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data), 1)

        # 2. Add collaborator from same university with DESIGNER role
        add_data = {
            "student_id": self.student_dev.id,
            "role": "designer",
            "status": "active"
        }
        res_add = self.client.post(url, add_data, format='json')
        self.assertEqual(res_add.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_add.data['role'], "designer")
        self.assertTrue(pitch.student_team.filter(id=self.student_dev.id).exists())

        # 3. Reject collaborator from unrelated university
        bad_add = {
            "student_id": self.student_other_uni.id,
            "role": "developer"
        }
        res_bad = self.client.post(url, bad_add, format='json')
        self.assertEqual(res_bad.status_code, status.HTTP_400_BAD_REQUEST)

        # 4. Reject unauthorized user attempting to modify team
        self.client.force_authenticate(user=self.student_other_uni)
        res_unauth = self.client.post(url, add_data, format='json')
        self.assertEqual(res_unauth.status_code, status.HTTP_403_FORBIDDEN)

    # =========================================================================
    # Issue 18/40: Discussion System (Challenges & Solutions)
    # =========================================================================

    def test_challenge_and_solution_discussions(self):
        """Citizens, students, and mentors can participate in challenge and solution discussions."""
        # 1. Challenge Discussion
        self.client.force_authenticate(user=self.citizen)
        res_chal = self.client.post(
            f"/api/issues/{self.issue.id}/discussions/",
            {"content": "Is the arsenic level worse during the post-monsoon dry season?"},
            format='json'
        )
        self.assertEqual(res_chal.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_chal.data['target_type'], 'challenge')

        # 2. Solution Technical Discussion
        pitch = Pitch.objects.create(
            issue=self.issue,
            university=self.uni_a,
            title="Catalytic Iron Cartridge",
            public_summary="Catalytic filtration.",
            confidential_package="Cartridge alloy formulation.",
            status=Pitch.Status.SUBMITTED
        )
        pitch.student_team.add(self.student_lead)

        self.client.force_authenticate(user=self.mentor_a)
        res_sol = self.client.post(
            f"/api/pitches/{pitch.id}/discussions/",
            {"content": "Have you calculated the pH dependency of iron hydroxide precipitation?"},
            format='json'
        )
        self.assertEqual(res_sol.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_sol.data['target_type'], 'solution')

        # 3. Retrieve discussions
        res_get_chal = self.client.get(f"/api/issues/{self.issue.id}/discussions/")
        self.assertEqual(res_get_chal.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_get_chal.data.get('results', res_get_chal.data)), 1)

        res_get_sol = self.client.get(f"/api/pitches/{pitch.id}/discussions/")
        self.assertEqual(res_get_sol.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_get_sol.data.get('results', res_get_sol.data)), 1)

    # =========================================================================
    # Acceptance Criteria Verification (Issue 19 & Section 33)
    # =========================================================================

    def test_challenge_acceptance_criteria_persisted(self):
        """Issue preserves and exposes acceptance criteria in serializer."""
        self.client.force_authenticate(user=self.coord_a)
        res = self.client.get(f"/api/issues/{self.issue.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("acceptance_criteria", res.data)
        self.assertEqual(res.data["acceptance_criteria"], self.issue.acceptance_criteria)
