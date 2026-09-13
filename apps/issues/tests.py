from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models import User, University
from apps.issues.models import Issue, Adoption, StudentNomination

class IssueLifecycleTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.uni = University.objects.create(name="Ranchi University", district="Ranchi")
        
        self.citizen = User.objects.create_user(
            email="citizen@jharkhand.in",
            name="Citizen Ramesh",
            role=User.Role.CITIZEN
        )
        self.coordinator = User.objects.create_user(
            email="coord@ranchiuniversity.ac.in",
            name="Coordinator RU",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni
        )
        self.student = User.objects.create_user(
            email="student@ranchiuniversity.ac.in",
            name="Student RU",
            role=User.Role.STUDENT,
            university=self.uni
        )
        self.admin = User.objects.create_user(
            email="admin@jharkhand.gov.in",
            name="Gov Admin",
            role=User.Role.GOV_ADMIN,
            is_staff=True
        )

    def test_citizen_submit_issue(self):
        self.client.force_authenticate(user=self.citizen)
        res = self.client.post("/api/issues/", {
            "title": "Broken solar micro-grid inverter in Bundu",
            "description": "The community solar unit has broken inverter capacitors causing blackouts.",
            "expected_outcome": "Rugged capacitor bank replacement and remote IoT monitoring.",
            "district": "Ranchi",
            "photo_url": "https://example.com/solar.jpg",
        })
        self.assertEqual(res.status_code, 201)
        issue_id = res.data['id']
        issue = Issue.objects.get(id=issue_id)
        self.assertEqual(issue.status, Issue.Status.SUBMITTED)
        # Automatic triage assigned ENERGY category
        self.assertEqual(issue.category, Issue.Category.ENERGY)

    def test_moderator_validate_issue(self):
        issue = Issue.objects.create(
            title="Paddy storage dampness",
            description="Fungus destroying rice harvest in storage godowns",
            expected_outcome="Humidity sensors and ventilation automation",
            district="Ranchi",
            photo_url="https://example.com/paddy.jpg",
            status=Issue.Status.SUBMITTED,
            submitted_by=self.citizen
        )
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(f"/api/issues/{issue.id}/moderate/", {
            "action": "validate"
        })
        self.assertEqual(res.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.VALIDATED)

    def test_student_nominate_and_coordinator_approve(self):
        issue = Issue.objects.create(
            title="Unadopted Forest challenge",
            description="Lack of non-timber forest produce processing unit",
            expected_outcome="Mini Mahua processing unit",
            district="Ranchi",
            photo_url="https://example.com/forest.jpg",
            status=Issue.Status.VALIDATED,
            submitted_by=self.citizen
        )
        # Student nominates
        self.client.force_authenticate(user=self.student)
        nom_res = self.client.post(f"/api/issues/{issue.id}/nominate/", {
            "rationale": "Our department has expertise in bio-processing equipment."
        })
        self.assertEqual(nom_res.status_code, 201)
        nom_id = nom_res.data['id']

        # Coordinator approves
        self.client.force_authenticate(user=self.coordinator)
        app_res = self.client.post(f"/api/issues/nominations/{nom_id}/review/", {
            "action": "approve"
        })
        self.assertEqual(app_res.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.ADOPTED)
        self.assertEqual(issue.adoption.mode, Adoption.Mode.NOMINATION_APPROVED)
