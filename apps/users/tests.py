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
