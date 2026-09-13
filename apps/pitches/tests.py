from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models import User, University
from apps.issues.models import Issue, Adoption
from apps.pitches.models import Pitch, CommunityFeedback, ProjectLifecycle

class PitchVaultAccessControlTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.uni = University.objects.create(name="BIT Sindri", district="Dhanbad")
        
        # Users
        self.coord = User.objects.create_user(
            email="coord@bitsindri.ac.in",
            name="Coordinator",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni
        )
        self.mentor = User.objects.create_user(
            email="mentor@bitsindri.ac.in",
            name="Mentor",
            role=User.Role.FACULTY_MENTOR,
            university=self.uni
        )
        self.student_a = User.objects.create_user(
            email="studentA@bitsindri.ac.in",
            name="Student Team A",
            role=User.Role.STUDENT,
            university=self.uni
        )
        self.student_b = User.objects.create_user(
            email="studentB@bitsindri.ac.in",
            name="Student Team B (Competitor)",
            role=User.Role.STUDENT,
            university=self.uni
        )
        self.citizen = User.objects.create_user(
            email="citizen@jharkhand.in",
            name="Citizen",
            role=User.Role.CITIZEN
        )

        # Issue & Adoption
        self.issue = Issue.objects.create(
            title="Clean Water for Topchanchi",
            description="Fluoride removal required",
            expected_outcome="Potable water",
            district="Dhanbad",
            photo_url="https://example.com/photo.jpg",
            status=Issue.Status.ADOPTED,
            submitted_by=self.citizen
        )
        self.adoption = Adoption.objects.create(
            issue=self.issue,
            university=self.uni,
            mode=Adoption.Mode.SELF_ADOPTED
        )

        # Pitch by Team A
        self.pitch_a = Pitch.objects.create(
            issue=self.issue,
            university=self.uni,
            title="Alumina Filter Solution",
            public_summary="A multi-tier filter using activated alumina",
            confidential_package="SECRET_PATENTED_IP_ALUMINA_NANOPARTICLES_RATIO_10:1",
            assigned_mentor=self.mentor
        )
        self.pitch_a.student_team.add(self.student_a)

    def test_submission_hash_automatically_generated(self):
        """Verify SHA-256 submission hash is created for prior art protection."""
        self.assertTrue(len(self.pitch_a.submission_hash) == 64)

    def test_submitting_student_can_read_confidential_package(self):
        """Author student team can view their own confidential technical package."""
        self.client.force_authenticate(user=self.student_a)
        res = self.client.get(f"/api/pitches/{self.pitch_a.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("SECRET_PATENTED_IP", res.data['confidential_package'])

    def test_competing_student_cannot_read_confidential_package(self):
        """CRITICAL: Competing student pitching on the same issue CANNOT see confidential package."""
        self.client.force_authenticate(user=self.student_b)
        res = self.client.get(f"/api/pitches/{self.pitch_a.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("SECRET_PATENTED_IP", res.data['confidential_package'])
        self.assertIn("PROTECTED", res.data['confidential_package'])
        # Public summary is visible
        self.assertEqual(res.data['public_summary'], self.pitch_a.public_summary)

    def test_citizen_cannot_read_confidential_package(self):
        """Citizen can see public summary but is blocked from confidential IP."""
        self.client.force_authenticate(user=self.citizen)
        res = self.client.get(f"/api/pitches/{self.pitch_a.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("SECRET_PATENTED_IP", res.data['confidential_package'])

    def test_university_coordinator_can_read_confidential_package(self):
        """University coordinator running the review board can inspect the confidential package."""
        self.client.force_authenticate(user=self.coord)
        res = self.client.get(f"/api/pitches/{self.pitch_a.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("SECRET_PATENTED_IP", res.data['confidential_package'])

    def test_review_board_select_winner(self):
        """Coordinator selects winning pitch, transitions issue to 'assigned' and creates lifecycle."""
        self.client.force_authenticate(user=self.coord)
        res = self.client.post(f"/api/pitches/{self.pitch_a.id}/review-action/", {
            "action": "select_winner",
            "review_feedback": "Excellent technical feasibility."
        })
        self.assertEqual(res.status_code, 200)
        self.pitch_a.refresh_from_db()
        self.issue.refresh_from_db()
        self.assertEqual(self.pitch_a.status, Pitch.Status.SELECTED)
        self.assertEqual(self.issue.status, Issue.Status.ASSIGNED)
        self.assertTrue(ProjectLifecycle.objects.filter(pitch=self.pitch_a).exists())

    def test_review_board_merge_pitches(self):
        """Coordinator can merge two complementary pitches into one joint team."""
        pitch_b = Pitch.objects.create(
            issue=self.issue,
            university=self.uni,
            title="Bio-sand stage",
            public_summary="Biological sand filtration",
            confidential_package="SECRET_SAND_SPEC"
        )
        pitch_b.student_team.add(self.student_b)

        self.client.force_authenticate(user=self.coord)
        res = self.client.post(f"/api/pitches/{self.pitch_a.id}/review-action/", {
            "action": "merge_pitches",
            "merge_with_pitch_id": pitch_b.id
        })
        self.assertEqual(res.status_code, 200)
        self.pitch_a.refresh_from_db()
        pitch_b.refresh_from_db()
        self.assertEqual(self.pitch_a.status, Pitch.Status.SELECTED)
        self.assertEqual(pitch_b.status, Pitch.Status.MERGED)
        # Student B is now included in pitch_a's joint team
        self.assertTrue(self.pitch_a.student_team.filter(id=self.student_b.id).exists())

    def test_government_cannot_read_confidential_package(self):
        """Government has No access to raw student confidential package (Image 3 Matrix)."""
        gov_admin = User.objects.create_user(
            email="admin@jharkhand.gov.in",
            name="Gov Admin",
            role=User.Role.GOV_ADMIN
        )
        self.client.force_authenticate(user=gov_admin)
        res = self.client.get(f"/api/pitches/{self.pitch_a.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("SECRET_PATENTED_IP", res.data['confidential_package'])
        self.assertIn("PROTECTED", res.data['confidential_package'])

    def test_community_feedback_visibility_matrix(self):
        """Community feedback is visible to student team only if shared by mentor (Image 3 Matrix)."""
        fb1 = CommunityFeedback.objects.create(
            pitch=self.pitch_a,
            citizen=self.citizen,
            feedback_text="Great initiative, but what about seasonal silt?",
            is_shared_with_students=False
        )
        fb2 = CommunityFeedback.objects.create(
            pitch=self.pitch_a,
            citizen=self.citizen,
            feedback_text="Power supply cuts every afternoon in Topchanchi.",
            is_shared_with_students=True
        )

        # 1. Author student team only sees shared feedback
        self.client.force_authenticate(user=self.student_a)
        res_a = self.client.get(f"/api/pitches/{self.pitch_a.id}/")
        self.assertEqual(len(res_a.data['community_feedback']), 1)
        self.assertEqual(res_a.data['community_feedback'][0]['id'], fb2.id)

        # 2. Competing student sees no feedback for this pitch
        self.client.force_authenticate(user=self.student_b)
        res_b = self.client.get(f"/api/pitches/{self.pitch_a.id}/")
        self.assertEqual(len(res_b.data['community_feedback']), 0)

        # 3. University coordinator and mentor see full feedback
        self.client.force_authenticate(user=self.coord)
        res_coord = self.client.get(f"/api/pitches/{self.pitch_a.id}/")
        self.assertEqual(len(res_coord.data['community_feedback']), 2)
