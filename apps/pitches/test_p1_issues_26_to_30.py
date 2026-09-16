from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.users.models import User, University
from apps.issues.models import Issue, Adoption, OpenCall, StudentNomination
from apps.pitches.models import Pitch, SolutionEvaluation


class P1Issues26To30TestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Universities
        self.uni_a = University.objects.create(name="BIT Sindri", district="Dhanbad")
        self.uni_b = University.objects.create(name="Ranchi University", district="Ranchi")

        # Users
        self.citizen = User.objects.create_user(
            email="citizen_26@jharkhand.in",
            name="Citizen Reporter",
            role=User.Role.CITIZEN
        )
        self.coord_a = User.objects.create_user(
            email="coord_26@bitsindri.ac.in",
            name="Coordinator BIT",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_a
        )
        self.coord_b = User.objects.create_user(
            email="coord_26@ranchi.ac.in",
            name="Coordinator RU",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni_b
        )
        self.mentor_a = User.objects.create_user(
            email="mentor_prof_a@bitsindri.ac.in",
            name="Prof. Sharma (BIT Mentor)",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni_a
        )
        self.mentor_b = User.objects.create_user(
            email="mentor_prof_b@ranchi.ac.in",
            name="Prof. Verma (RU Mentor)",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni_b
        )
        self.mentor_unassigned = User.objects.create_user(
            email="mentor_unassigned@bitsindri.ac.in",
            name="Prof. Unassigned (BIT)",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni_a
        )
        self.student = User.objects.create_user(
            email="student_lead_26@bitsindri.ac.in",
            name="Student Leader",
            role=User.Role.STUDENT,
            university=self.uni_a
        )

        # Issue and Adoption
        self.issue = Issue.objects.create(
            title="Clean Water Filtration for Topchanchi",
            description="High iron contamination in drinking water sources across rural Topchanchi.",
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
            title="Low-Cost Biochar Sand Filtration Unit",
            public_summary="Gravity-fed sand filtration enriched with local agricultural biochar.",
            confidential_package="Uses activated porous biochar to absorb iron and heavy metals. Supplies 5,000 liters/day.",
            repository_url="https://github.com/bitsindri/biochar-filter",
            status=Pitch.Status.SUBMITTED
        )
        self.pitch.student_team.add(self.student)

    # -------------------------------------------------------------
    # Issue 26: University Challenge Operational Center
    # -------------------------------------------------------------
    def test_issue_challenge_operational_context(self):
        """Verify issue details endpoint returns adoption info, status, and related context."""
        self.client.force_authenticate(user=self.coord_a)
        response = self.client.get(f"/api/issues/{self.issue.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["id"], self.issue.id)
        self.assertEqual(data["status"], "adopted")
        self.assertIsNotNone(data.get("adoption_details"))
        self.assertEqual(data["adoption_details"]["university"], self.uni_a.id)

    # -------------------------------------------------------------
    # Issue 28: Review Authorization
    # -------------------------------------------------------------
    def test_unauthorized_university_coordinator_cannot_execute_review_action(self):
        """Coordinators from other universities cannot execute review actions (403 Forbidden)."""
        self.client.force_authenticate(user=self.coord_b)
        response = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {"action": "start_review"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue("review" in str(response.data).lower() or "permission" in str(response.data).lower())

    def test_unassigned_faculty_mentor_cannot_execute_review_action(self):
        """Faculty mentors who are NOT assigned to this pitch cannot execute review actions (403 Forbidden)."""
        self.client.force_authenticate(user=self.mentor_unassigned)
        response = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {"action": "start_review"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue("review" in str(response.data).lower() or "permission" in str(response.data).lower())

    def test_student_cannot_execute_review_action(self):
        """Students cannot execute review actions (403 Forbidden)."""
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {"action": "start_review"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------
    # Issue 29: Mentor Assignment Validation
    # -------------------------------------------------------------
    def test_mentor_assignment_rejects_non_faculty_mentor_role(self):
        """Assigning a user who does not have the 'faculty_mentor' role returns 400 Bad Request."""
        self.client.force_authenticate(user=self.coord_a)
        response = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {"action": "assign_mentor", "mentor_id": self.student.id}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("faculty_mentor", response.data["error"].lower())

    def test_mentor_assignment_rejects_mentor_from_different_university(self):
        """Assigning a faculty mentor from a different university returns 400 Bad Request."""
        self.client.force_authenticate(user=self.coord_a)
        response = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {"action": "assign_mentor", "mentor_id": self.mentor_b.id}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("maintaining university", response.data["error"].lower())

    def test_mentor_assignment_succeeds_for_valid_university_mentor(self):
        """University coordinator can successfully assign an accredited faculty mentor from the same university."""
        self.client.force_authenticate(user=self.coord_a)
        response = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {"action": "assign_mentor", "mentor_id": self.mentor_a.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pitch.refresh_from_db()
        self.assertEqual(self.pitch.assigned_mentor_id, self.mentor_a.id)

    # -------------------------------------------------------------
    # Issue 27: University Review Actions (Coordinator & Assigned Mentor)
    # -------------------------------------------------------------
    def test_assigned_mentor_can_start_review_and_request_changes(self):
        """Once assigned, faculty mentor is authorized to start review and request changes."""
        self.pitch.assigned_mentor = self.mentor_a
        self.pitch.save()

        # Mentor starts review
        self.client.force_authenticate(user=self.mentor_a)
        res_start = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {"action": "start_review"}
        )
        self.assertEqual(res_start.status_code, status.HTTP_200_OK)
        self.pitch.refresh_from_db()
        self.assertEqual(self.pitch.status, Pitch.Status.UNDER_REVIEW)

        # Mentor requests changes
        res_changes = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {
                "action": "request_changes",
                "review_feedback": "Please add laboratory test results for water turbidity."
            }
        )
        self.assertEqual(res_changes.status_code, status.HTTP_200_OK)
        self.pitch.refresh_from_db()
        self.assertEqual(self.pitch.status, Pitch.Status.CHANGES_REQUESTED)
        self.assertEqual(self.pitch.review_feedback, "Please add laboratory test results for water turbidity.")

    def test_faculty_mentor_cannot_assign_mentors_or_select_winner(self):
        """Faculty mentor cannot assign other mentors or finalize winner (coordinator only)."""
        self.pitch.assigned_mentor = self.mentor_a
        self.pitch.save()

        self.client.force_authenticate(user=self.mentor_a)
        res_winner = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {"action": "select_winner"}
        )
        self.assertEqual(res_winner.status_code, status.HTTP_403_FORBIDDEN)

        res_assign = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {"action": "assign_mentor", "mentor_id": self.mentor_unassigned.id}
        )
        self.assertEqual(res_assign.status_code, status.HTTP_403_FORBIDDEN)

    def test_coordinator_can_select_winner(self):
        """University coordinator can select the winning pitch."""
        self.client.force_authenticate(user=self.coord_a)
        response = self.client.post(
            f"/api/pitches/{self.pitch.id}/review_action/",
            {"action": "select_winner", "review_feedback": "Outstanding engineering prototype."}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pitch.refresh_from_db()
        self.assertEqual(self.pitch.status, Pitch.Status.SELECTED)

    # -------------------------------------------------------------
    # Issue 30: Multi-Criteria Evaluation System
    # -------------------------------------------------------------
    def test_multi_criteria_evaluation_persistence_and_total_calculation(self):
        """Evaluation persists all 7 criteria and calculates total score out of 100."""
        self.pitch.assigned_mentor = self.mentor_a
        self.pitch.save()

        self.client.force_authenticate(user=self.mentor_a)
        eval_payload = {
            "technical_feasibility": 18,     # /20
            "social_impact": 19,            # /20
            "cost_feasibility": 14,         # /15
            "scalability": 13,              # /15
            "sustainability": 9,            # /10
            "innovation": 8,                # /10
            "implementation_readiness": 9,  # /10
            "recommendation": "select",
            "comments": "Exceptional practical potential. High community suitability for Dhanbad."
        }
        # Expected total: 18 + 19 + 14 + 13 + 9 + 8 + 9 = 90 / 100
        response = self.client.post(
            f"/api/pitches/{self.pitch.id}/evaluations/",
            eval_payload
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertEqual(data["total_score"], 90)
        self.assertEqual(data["recommendation"], "select")
        self.assertEqual(data["reviewer_details"]["id"], self.mentor_a.id)

        # Check in database
        eval_obj = SolutionEvaluation.objects.get(pitch=self.pitch, reviewer=self.mentor_a)
        self.assertEqual(eval_obj.total_score, 90)
        self.assertEqual(eval_obj.technical_feasibility, 18)
        self.assertEqual(eval_obj.social_impact, 19)

    def test_multi_criteria_evaluation_rejects_out_of_bounds_scores(self):
        """Validation fails if criteria score exceeds maximum allowed points."""
        self.pitch.assigned_mentor = self.mentor_a
        self.pitch.save()

        self.client.force_authenticate(user=self.mentor_a)
        invalid_payload = {
            "technical_feasibility": 25,    # Max is 20!
            "social_impact": 15,
            "cost_feasibility": 10,
            "scalability": 10,
            "sustainability": 8,
            "innovation": 8,
            "implementation_readiness": 8,
            "recommendation": "select",
            "comments": "Test out of bounds"
        }
        response = self.client.post(
            f"/api/pitches/{self.pitch.id}/evaluations/",
            invalid_payload
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("technical_feasibility", response.data)

    def test_multi_criteria_evaluation_rejects_unauthorized_user(self):
        """Unassigned faculty mentor or coordinator from different university cannot evaluate (403)."""
        self.client.force_authenticate(user=self.mentor_unassigned)
        eval_payload = {
            "technical_feasibility": 15,
            "social_impact": 15,
            "cost_feasibility": 10,
            "scalability": 10,
            "sustainability": 8,
            "innovation": 8,
            "implementation_readiness": 8,
            "recommendation": "select",
            "comments": "Attempt by unassigned mentor"
        }
        response = self.client.post(
            f"/api/pitches/{self.pitch.id}/evaluations/",
            eval_payload
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
