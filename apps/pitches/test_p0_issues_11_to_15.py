from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.users.models import User, University, Organization
from apps.issues.models import Issue, Adoption
from apps.pitches.models import Pitch, SolutionEvaluation, ProjectLifecycle


class P0Issues11To15TestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Universities
        self.uni_a = University.objects.create(name="BIT Sindri", district="Dhanbad")
        self.uni_b = University.objects.create(name="Ranchi University", district="Ranchi")

        # Users
        self.gov_admin = User.objects.create_user(
            email="gov_admin@jharkhand.gov.in",
            name="Gov Admin",
            role=User.Role.GOV_ADMIN
        )
        self.citizen = User.objects.create_user(
            email="citizen@jharkhand.in",
            name="Citizen Ramesh",
            role=User.Role.CITIZEN
        )
        self.coord_a1 = User.objects.create_user(
            email="coord1@bitsindri.ac.in",
            name="Coordinator 1 BIT",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_a
        )
        self.coord_a2 = User.objects.create_user(
            email="coord2@bitsindri.ac.in",
            name="Coordinator 2 BIT",
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
            email="mentor_a@bitsindri.ac.in",
            name="Prof Sharma",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni_a
        )
        self.student_a1 = User.objects.create_user(
            email="student_a1@bitsindri.ac.in",
            name="Student A1",
            role=User.Role.STUDENT,
            university=self.uni_a
        )
        self.student_a2 = User.objects.create_user(
            email="student_a2@bitsindri.ac.in",
            name="Student A2 (Competing Team)",
            role=User.Role.STUDENT,
            university=self.uni_a
        )

        # Issue submitted by citizen and adopted by uni_a
        self.issue = Issue.objects.create(
            title="Contaminated Wells in Jharia",
            description="High arsenic and fluoride content in 4 community borewells.",
            category="water_sanitation",
            district="Dhanbad",
            address="Ward 4 Jharia",
            submitted_by=self.citizen,
            status=Issue.Status.ADOPTED
        )
        self.adoption = Adoption.objects.create(
            issue=self.issue,
            university=self.uni_a,
            coordinator=self.coord_a1
        )

        # Pitch by Team A1
        self.pitch_1 = Pitch.objects.create(
            issue=self.issue,
            university=self.uni_a,
            title="Solar Electro-Coagulation Filter",
            public_summary="Clean drinking water using low-cost solar electrolysis.",
            confidential_package="Proprietary electrode alloy specs and firmware code.",
            status=Pitch.Status.SUBMITTED
        )
        self.pitch_1.student_team.add(self.student_a1)

        # Competing Pitch by Team A2
        self.pitch_2 = Pitch.objects.create(
            issue=self.issue,
            university=self.uni_a,
            title="Bio-Sand and Moringa Seed Purifier",
            public_summary="Biological sand filtration enhanced with moringa seed powder.",
            confidential_package="Biochemical filtration ratios and seed preparation protocols.",
            status=Pitch.Status.SUBMITTED
        )
        self.pitch_2.student_team.add(self.student_a2)

    # =========================================================================
    # Issue 12: Real Evaluation Persistence & Multi-Criteria Scoring
    # =========================================================================

    def test_submit_valid_evaluation_and_calculate_total(self):
        """Reviewer evaluates solution with multi-criteria scores; total score is persisted."""
        self.client.force_authenticate(user=self.coord_a1)
        url = f"/api/pitches/{self.pitch_1.id}/evaluations/"
        data = {
            "technical_feasibility": 18,
            "social_impact": 19,
            "cost_feasibility": 14,
            "scalability": 13,
            "sustainability": 9,
            "innovation": 8,
            "implementation_readiness": 9,
            "recommendation": "select",
            "comments": "Outstanding technical rigor and highly suitable for local deployment."
        }
        res = self.client.post(url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Verify persisted evaluation
        eval_obj = SolutionEvaluation.objects.get(pitch=self.pitch_1, reviewer=self.coord_a1)
        expected_total = 18 + 19 + 14 + 13 + 9 + 8 + 9  # 90/100
        self.assertEqual(eval_obj.total_score, expected_total)
        self.assertEqual(eval_obj.total_score, 90)
        self.assertEqual(eval_obj.recommendation, "select")
        self.assertEqual(eval_obj.comments, data["comments"])

    def test_evaluation_upsert_behavior(self):
        """Re-submitting evaluation by same reviewer updates existing record."""
        self.client.force_authenticate(user=self.coord_a1)
        url = f"/api/pitches/{self.pitch_1.id}/evaluations/"
        initial_data = {
            "technical_feasibility": 15,
            "social_impact": 15,
            "cost_feasibility": 10,
            "scalability": 10,
            "sustainability": 5,
            "innovation": 5,
            "implementation_readiness": 5,
            "recommendation": "request_changes",
            "comments": "Need more data on electrode corrosion."
        }
        res1 = self.client.post(url, initial_data, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SolutionEvaluation.objects.filter(pitch=self.pitch_1).count(), 1)

        # Update evaluation
        updated_data = initial_data.copy()
        updated_data["technical_feasibility"] = 20
        updated_data["recommendation"] = "select"
        res2 = self.client.post(url, updated_data, format='json')
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

        # Still only 1 record, but updated total score
        self.assertEqual(SolutionEvaluation.objects.filter(pitch=self.pitch_1).count(), 1)
        eval_obj = SolutionEvaluation.objects.get(pitch=self.pitch_1)
        self.assertEqual(eval_obj.technical_feasibility, 20)
        self.assertEqual(eval_obj.recommendation, "select")
        self.assertEqual(eval_obj.total_score, 70)

    def test_evaluation_score_bounds_validation(self):
        """Evaluations reject scores exceeding criteria maximums or below zero."""
        self.client.force_authenticate(user=self.coord_a1)
        url = f"/api/pitches/{self.pitch_1.id}/evaluations/"

        # technical_feasibility max is 20
        bad_data_1 = {"technical_feasibility": 25, "social_impact": 10}
        res1 = self.client.post(url, bad_data_1, format='json')
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("technical_feasibility", res1.data)

        # sustainability max is 10
        bad_data_2 = {"sustainability": 15}
        res2 = self.client.post(url, bad_data_2, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sustainability", res2.data)

        # negative score
        bad_data_3 = {"cost_feasibility": -5}
        res3 = self.client.post(url, bad_data_3, format='json')
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cost_feasibility", res3.data)

    # =========================================================================
    # Issue 13: Strict Resource-Level Permissions
    # =========================================================================

    def test_reviewer_from_unrelated_university_forbidden(self):
        """Reviewer from University B cannot evaluate pitch belonging to University A."""
        self.client.force_authenticate(user=self.coord_b)
        url = f"/api/pitches/{self.pitch_1.id}/evaluations/"
        data = {"technical_feasibility": 15, "social_impact": 15}
        res = self.client.post(url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_and_citizen_cannot_submit_evaluation(self):
        """Students and citizens are blocked from submitting evaluations."""
        # Student
        self.client.force_authenticate(user=self.student_a1)
        url = f"/api/pitches/{self.pitch_1.id}/evaluations/"
        res_student = self.client.post(url, {"technical_feasibility": 15}, format='json')
        self.assertEqual(res_student.status_code, status.HTTP_403_FORBIDDEN)

        # Citizen
        self.client.force_authenticate(user=self.citizen)
        res_citizen = self.client.post(url, {"technical_feasibility": 15}, format='json')
        self.assertEqual(res_citizen.status_code, status.HTTP_403_FORBIDDEN)

    def test_evaluation_access_control_competing_teams_and_public(self):
        """
        Submitting student team can view evaluations for their pitch.
        Competing student teams and public citizens cannot view evaluations.
        """
        # Create evaluation by coord_a1
        eval_obj = SolutionEvaluation.objects.create(
            pitch=self.pitch_1,
            reviewer=self.coord_a1,
            technical_feasibility=18,
            social_impact=18,
            cost_feasibility=12,
            scalability=12,
            sustainability=8,
            innovation=8,
            implementation_readiness=8,
            recommendation="select",
            comments="Very strong submission."
        )

        # 1. Submitting student team can view via evaluations list endpoint
        self.client.force_authenticate(user=self.student_a1)
        res_own = self.client.get(f"/api/pitches/{self.pitch_1.id}/evaluations/")
        self.assertEqual(res_own.status_code, status.HTTP_200_OK)
        results = res_own.data.get('results', res_own.data)
        self.assertEqual(len(results), 1)

        # 2. Competing student team cannot view via evaluations list endpoint
        self.client.force_authenticate(user=self.student_a2)
        res_competing = self.client.get(f"/api/pitches/{self.pitch_1.id}/evaluations/")
        self.assertEqual(res_competing.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Competing student team viewing Pitch detail sees evaluations masked/empty
        res_pitch_competing = self.client.get(f"/api/pitches/{self.pitch_1.id}/")
        self.assertEqual(res_pitch_competing.status_code, status.HTTP_200_OK)
        self.assertEqual(res_pitch_competing.data['evaluations'], [])

        # 4. Own student team viewing Pitch detail sees evaluations
        self.client.force_authenticate(user=self.student_a1)
        res_pitch_own = self.client.get(f"/api/pitches/{self.pitch_1.id}/")
        self.assertEqual(res_pitch_own.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_pitch_own.data['evaluations']), 1)

    def test_only_author_or_staff_can_edit_evaluation(self):
        """Coordinator 2 cannot edit Coordinator 1's evaluation."""
        eval_obj = SolutionEvaluation.objects.create(
            pitch=self.pitch_1,
            reviewer=self.coord_a1,
            technical_feasibility=15,
            recommendation="request_changes"
        )
        url = f"/api/pitches/evaluations/{eval_obj.id}/"

        # Coordinator 2 tries to edit
        self.client.force_authenticate(user=self.coord_a2)
        res = self.client.patch(url, {"technical_feasibility": 20}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Author coordinator edits successfully
        self.client.force_authenticate(user=self.coord_a1)
        res_author = self.client.patch(url, {"technical_feasibility": 20}, format='json')
        self.assertEqual(res_author.status_code, status.HTTP_200_OK)
        eval_obj.refresh_from_db()
        self.assertEqual(eval_obj.technical_feasibility, 20)

    def test_issue_moderation_strictly_gov_admin_or_staff(self):
        """University coordinator cannot moderate issue; only gov_admin or staff can."""
        self.issue.status = Issue.Status.VALIDATING
        self.issue.save()
        url = f"/api/issues/{self.issue.id}/moderate/"

        # Coordinator attempts to validate
        self.client.force_authenticate(user=self.coord_a1)
        res_coord = self.client.post(url, {"action": "validate"}, format='json')
        self.assertEqual(res_coord.status_code, status.HTTP_403_FORBIDDEN)

        # Gov admin validates successfully
        self.client.force_authenticate(user=self.gov_admin)
        res_gov = self.client.post(url, {"action": "validate"}, format='json')
        self.assertEqual(res_gov.status_code, status.HTTP_200_OK)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.VALIDATED)

    # =========================================================================
    # Issue 11: Deep-Link Safe Detail Endpoints
    # =========================================================================

    def test_deep_link_direct_retrieval_endpoints(self):
        """Direct retrieval of pitch and evaluation by ID via standalone deep-link endpoints."""
        eval_obj = SolutionEvaluation.objects.create(
            pitch=self.pitch_1,
            reviewer=self.coord_a1,
            technical_feasibility=17,
            social_impact=18,
            recommendation="select"
        )

        self.client.force_authenticate(user=self.coord_a1)

        # Standalone pitch detail
        res_pitch = self.client.get(f"/api/pitches/{self.pitch_1.id}/")
        self.assertEqual(res_pitch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_pitch.data['id'], self.pitch_1.id)
        self.assertEqual(res_pitch.data['title'], self.pitch_1.title)

        # Standalone evaluation detail
        res_eval = self.client.get(f"/api/pitches/evaluations/{eval_obj.id}/")
        self.assertEqual(res_eval.status_code, status.HTTP_200_OK)
        self.assertEqual(res_eval.data['id'], eval_obj.id)
        self.assertEqual(res_eval.data['technical_feasibility'], 17)

    # =========================================================================
    # Issue 14 & 15: Status Contract & Review Board Lifecycle Cohesion
    # =========================================================================

    def test_review_board_select_winner_and_mentor_assignment(self):
        """Review board selects winner, transitions issue to assigned, and auto-rejects competing pitch."""
        self.client.force_authenticate(user=self.coord_a1)
        url = f"/api/pitches/{self.pitch_1.id}/review-action/"

        # Assign mentor from same university
        res_mentor = self.client.post(url, {"action": "assign_mentor", "mentor_id": self.mentor_a.id}, format='json')
        self.assertEqual(res_mentor.status_code, status.HTTP_200_OK)
        self.pitch_1.refresh_from_db()
        self.assertEqual(self.pitch_1.assigned_mentor, self.mentor_a)

        # Select winner
        res_select = self.client.post(url, {
            "action": "select_winner",
            "review_feedback": "Selected for field deployment in Jharia."
        }, format='json')
        self.assertEqual(res_select.status_code, status.HTTP_200_OK)

        self.pitch_1.refresh_from_db()
        self.assertEqual(self.pitch_1.status, Pitch.Status.SELECTED)

        # Issue transitions to assigned
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.ASSIGNED)

        # Competing pitch 2 is auto-rejected
        self.pitch_2.refresh_from_db()
        self.assertEqual(self.pitch_2.status, Pitch.Status.REJECTED)
