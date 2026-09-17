from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models import User, University, Organization

class UserAuthTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.uni = University.objects.create(name="NIT Jamshedpur", district="East Singhbhum")
        self.org = Organization.objects.create(name="Tata Steel Foundation", org_type="csr")

    def test_user_registration_and_login(self):
        # Register student
        reg_res = self.client.post("/api/auth/register/", {
            "email": "student_test@nitjsr.ac.in",
            "password": "SecurePassword123",
            "name": "Test Student",
            "role": "student",
            "university": self.uni.id
        })
        self.assertEqual(reg_res.status_code, 201)
        self.assertEqual(reg_res.data['email'], "student_test@nitjsr.ac.in")

        # Login and obtain JWT tokens
        login_res = self.client.post("/api/auth/login/", {
            "email": "student_test@nitjsr.ac.in",
            "password": "SecurePassword123"
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("access", login_res.data)
        self.assertIn("user", login_res.data)
        self.assertEqual(login_res.data['user']['role'], "student")

    def test_profile_access_authenticated(self):
        user = User.objects.create_user(
            email="citizen_test@jharkhand.in",
            password="SecurePassword123",
            name="Citizen Test",
            role=User.Role.CITIZEN
        )
        self.client.force_authenticate(user=user)
        res = self.client.get("/api/auth/profile/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['name'], "Citizen Test")

    def test_privileged_roles_cannot_self_register(self):
        privileged_roles = ["gov_admin", "university_coordinator", "faculty_mentor", "industry_partner"]
        for role in privileged_roles:
            res = self.client.post("/api/auth/register/", {
                "email": f"attacker_{role}@example.com",
                "password": "Password123",
                "name": "Attacker",
                "role": role,
                "university": self.uni.id,
                "organization": self.org.id
            })
            self.assertEqual(res.status_code, 400, f"Role {role} should not be allowed to self-register")
            self.assertIn("role", res.data)

    def test_student_registration_requires_university(self):
        res = self.client.post("/api/auth/register/", {
            "email": "student_nouni@example.com",
            "password": "Password123",
            "name": "Student Without Uni",
            "role": "student"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("university", res.data)

    def test_citizen_registration_clears_affiliations(self):
        res = self.client.post("/api/auth/register/", {
            "email": "citizen_valid@jharkhand.in",
            "password": "Password123",
            "name": "Citizen User",
            "role": "citizen",
            "university": self.uni.id,
            "organization": self.org.id
        })
        self.assertEqual(res.status_code, 201)
        user = User.objects.get(email="citizen_valid@jharkhand.in")
        self.assertEqual(user.role, User.Role.CITIZEN)
        self.assertIsNone(user.university)
        self.assertIsNone(user.organization)

