from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models import User, University, Organization
from apps.issues.models import Issue, Adoption
from apps.pitches.models import Pitch
from apps.engagements.models import IndustryEngagement

class IndustryEngagementTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.uni = University.objects.create(name="BIT Sindri", district="Dhanbad")
        self.org = Organization.objects.create(name="Tata Steel Foundation", org_type="csr")

        self.coord = User.objects.create_user(
            email="coord@bitsindri.ac.in",
            name="Coordinator",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.uni
        )
        self.industry_user = User.objects.create_user(
            email="csr@tatasteel.com",
            name="Industry Lead",
            role=User.Role.INDUSTRY_PARTNER,
            organization=self.org
        )
        self.citizen = User.objects.create_user(
            email="citizen@jharkhand.in",
            name="Citizen",
            role=User.Role.CITIZEN
        )
        self.issue = Issue.objects.create(
            title="Industrial Slag Leachate Remediation",
            description="Leachate contaminating local pond",
            expected_outcome="Bio-remediation barrier",
            district="East Singhbhum",
            photo_url="https://example.com/slag.jpg",
            status=Issue.Status.ASSIGNED,
            submitted_by=self.citizen
        )

    def test_industry_initiates_partnership(self):
        self.client.force_authenticate(user=self.industry_user)
        res = self.client.post("/api/engagements/", {
            "issue": self.issue.id,
            "engagement_type": "funding",
            "proposal_notes": "Offering Rs 5,00,000 CSR funding for pilot testing."
        })
        self.assertEqual(res.status_code, 201)
        engagement_id = res.data['id']

        # Coordinator accepts partnership
        self.client.force_authenticate(user=self.coord)
        accept_res = self.client.post(f"/api/engagements/{engagement_id}/respond/", {
            "action": "accept",
            "response_notes": "Delighted to partner with Tata Steel Foundation."
        })
        self.assertEqual(accept_res.status_code, 200)
        self.assertEqual(accept_res.data['status'], IndustryEngagement.Status.ACCEPTED)
