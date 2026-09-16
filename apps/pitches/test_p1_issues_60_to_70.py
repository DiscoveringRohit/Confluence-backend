import json
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.users.models import User, University, Organization
from apps.issues.models import (
    Issue, Adoption, ChallengeAdoption, StudentNomination, ChallengeNomination,
    OpenCall, CitizenVerification, ActivityEvent, DiscussionComment, Discussion, Comment,
    log_activity
)
from apps.issues.serializers import (
    IssueSerializer, AdoptionSerializer, ChallengeAdoptionSerializer,
    StudentNominationSerializer, ChallengeNominationSerializer,
    OpenCallSerializer, CitizenVerificationSerializer, ActivityEventSerializer,
    DiscussionCommentSerializer, DiscussionSerializer, CommentSerializer
)
from apps.pitches.models import (
    Pitch, Solution, SolutionTeam, SolutionTeamMember, TeamMember,
    SolutionEvaluation, SolutionReview, PitchVersionHistory, Project,
    ProjectMilestone, Certificate
)
from apps.pitches.serializers import (
    PitchSerializer, SolutionSerializer, PitchCreateSerializer, SolutionCreateSerializer,
    SolutionTeamMemberSerializer, TeamMemberSerializer,
    SolutionEvaluationSerializer, SolutionReviewSerializer,
    ProjectSerializer, ProjectDetailSerializer, ProjectMilestoneSerializer
)


class Issues60To70TestCase(TestCase):
    """
    Test suite for Sections 60 to 70 of Confluence_Workflow_Gap_Analysis.md.
    Covers recommended core data models, aliases, property bindings, serializers, and full canonical state machine.
    """
    def setUp(self):
        self.client = APIClient()

        # Universities
        self.bit = University.objects.create(name="Birsa Institute of Technology Sindri", code="BITS", district="Dhanbad")
        self.nit = University.objects.create(name="NIT Jamshedpur", code="NITJ", district="East Singhbhum")

        # Users
        self.citizen = User.objects.create_user(
            email="citizen@jharkhand.in",
            password="Password@123",
            name="Ramesh Citizen",
            role=User.Role.CITIZEN
        )
        self.admin = User.objects.create_user(
            email="admin@jharkhand.gov.in",
            password="Password@123",
            name="State Admin",
            role=User.Role.GOV_ADMIN,
            is_staff=True
        )
        self.coordinator = User.objects.create_user(
            email="coordinator@bitsindri.ac.in",
            password="Password@123",
            name="Dr. Coordinator",
            role=User.Role.UNIVERSITY_COORDINATOR,
            university=self.bit
        )
        self.mentor = User.objects.create_user(
            email="mentor@bitsindri.ac.in",
            password="Password@123",
            name="Prof. Mentor",
            role=User.Role.FACULTY_MENTOR,
            university=self.bit
        )
        self.student = User.objects.create_user(
            email="student@bitsindri.ac.in",
            password="Password@123",
            name="Aman Student",
            role=User.Role.STUDENT,
            university=self.bit
        )
        self.student2 = User.objects.create_user(
            email="student2@bitsindri.ac.in",
            password="Password@123",
            name="Priya Student",
            role=User.Role.STUDENT,
            university=self.bit
        )

        # Base Challenge
        self.issue = Issue.objects.create(
            title="Solar Micro-Grid for Rural Health Clinic",
            description="Intermittent grid power causes medical refrigeration failures in rural clinic.",
            context="Rural health substation located in Tundi block serving 12,000 villagers.",
            expected_outcome="24/7 reliable solar-battery power system with automated telemetry monitoring.",
            requirements="Solar PV array >= 5kW, LiFePO4 battery storage, remote MQTT telemetry.",
            constraints="Budget limit of Rs 3.5 Lakhs, local monsoon weather tolerance.",
            acceptance_criteria="Continuous 48-hour cold chain preservation test under simulated power cuts.",
            category=Issue.Category.ENERGY,
            district="Dhanbad",
            address="Primary Health Center, Tundi Block",
            submitted_by=self.citizen,
            status=Issue.Status.VALIDATED,
            maintaining_university=self.bit
        )

    def test_issue_60_challenge_adoption_data_model(self):
        """
        Section 60: ChallengeAdoption data model specification & aliases.
        """
        self.assertEqual(ChallengeAdoption, Adoption)
        self.assertEqual(ChallengeAdoptionSerializer, AdoptionSerializer)

        adoption = ChallengeAdoption.objects.create(
            issue=self.issue,
            university=self.bit,
            coordinator=self.coordinator,
            status=Adoption.Status.APPROVED
        )

        # Verify property aliases
        self.assertEqual(adoption.challenge.id, self.issue.id)
        self.assertIsNotNone(adoption.created_at)
        self.assertIsNotNone(adoption.approved_at)

        # Serializer validation
        serializer = ChallengeAdoptionSerializer(adoption)
        data = serializer.data
        self.assertEqual(data['challenge'], self.issue.id)
        self.assertEqual(data['status'], 'approved')
        self.assertIn('approved_at', data)
        self.assertIn('created_at', data)

    def test_issue_61_open_call_data_model(self):
        """
        Section 61: OpenCall data model specification, fields, and challenge alias.
        """
        open_call = OpenCall.objects.create(
            issue=self.issue,
            university=self.bit,
            created_by=self.coordinator,
            title="Open Call: Micro-Grid Innovation Hackathon",
            description="Inviting student teams from Electrical & CSE to propose automated solar micro-grids.",
            opening_date="2026-10-01",
            closing_date="2026-10-31",
            eligibility="Pre-final and Final Year B.Tech Students",
            required_skills="Power electronics, Embedded C, IoT telemetry",
            departments="EEE, ECE, CSE",
            funding="Rs 50,000 Seed Grant",
            evaluation_criteria="Technical feasibility (30%), Cost efficiency (30%), Reliability (40%)",
            max_teams=8,
            status=OpenCall.Status.OPEN
        )

        # Verify property alias
        self.assertEqual(open_call.challenge.id, self.issue.id)

        # Serializer validation
        serializer = OpenCallSerializer(open_call)
        data = serializer.data
        self.assertEqual(data['challenge'], self.issue.id)
        self.assertEqual(data['title'], "Open Call: Micro-Grid Innovation Hackathon")
        self.assertEqual(data['funding'], "Rs 50,000 Seed Grant")
        self.assertEqual(data['max_teams'], 8)
        self.assertEqual(data['status'], 'open')

    def test_issue_62_solution_data_model(self):
        """
        Section 62: Solution data model specification, property accessors, and aliases.
        """
        self.assertEqual(Solution, Pitch)
        self.assertEqual(SolutionSerializer, PitchSerializer)
        self.assertEqual(SolutionCreateSerializer, PitchCreateSerializer)

        solution = Solution.objects.create(
            issue=self.issue,
            university=self.bit,
            title="SolarGuard: IoT-Monitored Micro-Grid",
            public_summary="Clean solar-battery hybrid backup with live cold-chain telemetry.",
            confidential_package="Inverter firmware schematic, MQTT broker configuration, and battery BMS design.",
            repository_url="https://github.com/innovators/solarguard",
            demo_url="https://solarguard-demo.jharkhand.in",
            documentation_url="https://docs.solarguard.jharkhand.in",
            video_url="https://youtu.be/solarguard_demo",
            status=Solution.Status.SUBMITTED
        )
        solution.student_team.add(self.student)

        # Verify property accessors
        self.assertEqual(solution.challenge.id, self.issue.id)
        self.assertEqual(solution.summary, "Clean solar-battery hybrid backup with live cold-chain telemetry.")
        self.assertEqual(solution.proposed_solution, "Clean solar-battery hybrid backup with live cold-chain telemetry.")
        self.assertEqual(solution.expected_impact, "Clean solar-battery hybrid backup with live cold-chain telemetry.")
        self.assertEqual(solution.private_details, "Inverter firmware schematic, MQTT broker configuration, and battery BMS design.")
        self.assertIn(self.student, solution.team.all())
        self.assertTrue(solution.public_id.startswith("SOL-"))

        # Serializer validation
        serializer = SolutionSerializer(solution)
        data = serializer.data
        self.assertEqual(data['challenge'], self.issue.id)
        self.assertEqual(data['summary'], solution.public_summary)
        self.assertEqual(data['proposed_solution'], solution.public_summary)
        self.assertEqual(data['expected_impact'], solution.public_summary)
        self.assertEqual(data['repository_url'], "https://github.com/innovators/solarguard")
        self.assertEqual(data['demo_url'], "https://solarguard-demo.jharkhand.in")

    def test_issue_63_solution_team_data_model(self):
        """
        Section 63: SolutionTeam & TeamMember model aliases & properties.
        """
        self.assertEqual(TeamMember, SolutionTeamMember)
        self.assertEqual(TeamMemberSerializer, SolutionTeamMemberSerializer)

        solution = Solution.objects.create(
            issue=self.issue,
            university=self.bit,
            title="WaterFilter IoT Solution",
            public_summary="Smart filtration unit.",
            confidential_package="Proprietary filter core."
        )
        member = TeamMember.objects.create(
            pitch=solution,
            student=self.student,
            role=TeamMember.Role.OWNER,
            status=TeamMember.Status.ACTIVE
        )

        # Verify property alias
        self.assertEqual(member.solution.id, solution.id)

        # Serializer validation
        serializer = TeamMemberSerializer(member)
        data = serializer.data
        self.assertEqual(data['solution'], solution.id)
        self.assertEqual(data['role'], 'owner')
        self.assertEqual(data['status'], 'active')

    def test_issue_64_solution_review_data_model(self):
        """
        Section 64: SolutionReview & SolutionEvaluation model aliases, properties, and decision binding.
        """
        self.assertEqual(SolutionReview, SolutionEvaluation)
        self.assertEqual(SolutionReviewSerializer, SolutionEvaluationSerializer)

        solution = Solution.objects.create(
            issue=self.issue,
            university=self.bit,
            title="CleanEnergy Telemetry",
            public_summary="Summary",
            confidential_package="Secret package"
        )
        review = SolutionReview.objects.create(
            pitch=solution,
            reviewer=self.mentor,
            technical_feasibility=18,
            social_impact=19,
            cost_feasibility=14,
            scalability=13,
            sustainability=9,
            innovation=9,
            implementation_readiness=8,
            recommendation=SolutionEvaluation.Recommendation.SELECT,
            comments="Outstanding technical readiness and strong social impact on rural clinics."
        )

        # Verify property accessors & calculation
        self.assertEqual(review.solution.id, solution.id)
        self.assertEqual(review.decision, 'select')
        self.assertEqual(review.total_score, 90)

        # Serializer validation
        serializer = SolutionReviewSerializer(review)
        data = serializer.data
        self.assertEqual(data['solution'], solution.id)
        self.assertEqual(data['decision'], 'select')
        self.assertEqual(data['total_score'], 90)

    def test_issue_65_project_core_data_model(self):
        """
        Section 65: Project core data model specification and relational binding.
        """
        solution = Solution.objects.create(
            issue=self.issue,
            university=self.bit,
            title="Solar Implementation Solution",
            public_summary="Public",
            confidential_package="Private",
            status=Solution.Status.SELECTED
        )
        project = Project.objects.create(
            solution=solution,
            challenge=self.issue,
            university=self.bit,
            mentor=self.mentor,
            title="Solar Implementation Project - Tundi Clinic",
            status=Project.Status.PROTOTYPE,
            start_date="2026-11-01",
            target_date="2027-01-31",
            deployment_status="prototype_testing",
            deployment_evidence="BMS prototype telemetry dashboard live link.",
            outcome="Prototype demonstrates 98.4% uptime across 14-day test run."
        )
        project.team.add(self.student, self.student2)

        # Verify project fields
        self.assertEqual(project.solution.id, solution.id)
        self.assertEqual(project.challenge.id, self.issue.id)
        self.assertEqual(project.mentor.id, self.mentor.id)
        self.assertEqual(project.team.count(), 2)
        self.assertTrue(project.public_id.startswith("PRJ-"))

        # Serializer validation
        serializer = ProjectSerializer(project)
        data = serializer.data
        self.assertEqual(data['challenge'], self.issue.id)
        self.assertEqual(data['solution'], solution.id)
        self.assertEqual(data['status'], 'prototype')
        self.assertEqual(data['deployment_status'], 'prototype_testing')
        self.assertEqual(data['challenge_details']['title'], self.issue.title)
        self.assertEqual(data['solution_details']['title'], solution.title)

    def test_issue_66_project_milestone_core_data_model(self):
        """
        Section 66: ProjectMilestone data model specification and review workflow.
        """
        solution = Solution.objects.create(
            issue=self.issue,
            university=self.bit,
            title="Smart Grid Solution",
            public_summary="Public",
            confidential_package="Private"
        )
        project = Project.objects.create(
            solution=solution,
            challenge=self.issue,
            university=self.bit,
            title="Smart Grid Deployment"
        )
        milestone = ProjectMilestone.objects.create(
            project=project,
            order=1,
            title="BMS Inverter Hardware Assembly & Lab Test",
            description="Assemble inverter chassis, connect LiFePO4 cells, calibrate telemetry current sensors.",
            due_date="30 days",
            owner=self.student,
            status=ProjectMilestone.Status.SUBMITTED,
            evidence="https://github.com/innovators/smart-grid/releases/tag/v1.0-hardware-lab-report",
            submitted_at=timezone.now()
        )

        # Mentor reviews milestone
        milestone.status = ProjectMilestone.Status.APPROVED
        milestone.reviewed_at = timezone.now()
        milestone.reviewer = self.mentor
        milestone.reviewer_feedback = "Telemetry accuracy verified within 0.5% margin. Approved."
        milestone.save()

        # Serializer validation
        serializer = ProjectMilestoneSerializer(milestone)
        data = serializer.data
        self.assertEqual(data['project'], project.id)
        self.assertEqual(data['status'], 'approved')
        self.assertEqual(data['owner'], self.student.id)
        self.assertEqual(data['reviewer'], self.mentor.id)
        self.assertIn("Telemetry accuracy verified", data['reviewer_feedback'])

    def test_issue_67_discussion_and_comment_data_model(self):
        """
        Section 67: Discussion & Comment model aliases, properties, and serializer bindings.
        """
        self.assertEqual(Discussion, DiscussionComment)
        self.assertEqual(Comment, DiscussionComment)
        self.assertEqual(DiscussionSerializer, DiscussionCommentSerializer)
        self.assertEqual(CommentSerializer, DiscussionCommentSerializer)

        solution = Solution.objects.create(
            issue=self.issue,
            university=self.bit,
            title="Telemetry Solution",
            public_summary="Summary",
            confidential_package="Details"
        )

        # Challenge Discussion
        disc1 = Discussion.objects.create(
            target_type=DiscussionComment.TargetType.CHALLENGE,
            issue=self.issue,
            author=self.student,
            category="requirements",
            content="Is there already a 3-phase connection at the Tundi clinic substation?"
        )
        self.assertEqual(disc1.challenge.id, self.issue.id)

        # Solution Comment
        disc2 = Comment.objects.create(
            target_type=DiscussionComment.TargetType.SOLUTION,
            pitch=solution,
            author=self.mentor,
            category="technical",
            content="Consider adding overvoltage surge protection at the DC bus inlet."
        )
        self.assertEqual(disc2.solution.id, solution.id)

        # Serializer validation
        ser1 = DiscussionSerializer(disc1)
        ser2 = CommentSerializer(disc2)
        self.assertEqual(ser1.data['challenge'], self.issue.id)
        self.assertEqual(ser2.data['solution'], solution.id)

    def test_issue_68_activity_event_data_model(self):
        """
        Section 68: ActivityEvent data model, challenge binding, and serializer.
        """
        event = log_activity(
            issue=self.issue,
            actor=self.coordinator,
            event_type="open_call_created",
            description="Open call announced for Solar Micro-Grid",
            object_type="open_call",
            object_id="1",
            metadata={"departments": ["EEE", "CSE"], "max_teams": 8}
        )

        # Verify challenge alias
        self.assertEqual(event.challenge.id, self.issue.id)

        # Serializer validation
        serializer = ActivityEventSerializer(event)
        data = serializer.data
        self.assertEqual(data['challenge'], self.issue.id)
        self.assertEqual(data['event_type'], 'open_call_created')
        self.assertEqual(data['actor'], self.coordinator.id)

    def test_issue_69_citizen_verification_data_model(self):
        """
        Section 69: CitizenVerification data model, challenge alias, and result outcomes.
        """
        verification = CitizenVerification.objects.create(
            issue=self.issue,
            citizen=self.citizen,
            result=CitizenVerification.Result.VERIFIED,
            reason="Solar micro-grid is operational and hospital vaccine cooler has maintained 4 deg C for 7 days uninterrupted.",
            evidence="Hospital logbook sign-off by Chief Medical Officer."
        )

        # Verify challenge alias
        self.assertEqual(verification.challenge.id, self.issue.id)
        self.assertEqual(verification.result, 'verified')

        # Serializer validation
        serializer = CitizenVerificationSerializer(verification)
        data = serializer.data
        self.assertEqual(data['challenge'], self.issue.id)
        self.assertEqual(data['result'], 'verified')
        self.assertIn("vaccine cooler has maintained", data['reason'])

    def test_issue_70_recommended_challenge_state_machine(self):
        """
        Section 70: Full canonical Challenge State Machine transition lifecycle.
        Validates all transitions defined in Section 70 specification.
        """
        issue = Issue.objects.create(
            title="Clean Water for Gov School",
            description="School requires filtration plant.",
            expected_outcome="Potable drinking water for 450 students.",
            district="Ranchi",
            submitted_by=self.citizen,
            status=Issue.Status.SUBMITTED
        )

        # 1. SUBMITTED -> VALIDATING
        issue.transition_status(Issue.Status.VALIDATING, actor=self.admin, reason="Initiating government moderation check.")
        self.assertEqual(issue.status, Issue.Status.VALIDATING)

        # 2. VALIDATING -> VALIDATED
        issue.transition_status(Issue.Status.VALIDATED, actor=self.admin, reason="Challenge validated as authentic civic need.")
        self.assertEqual(issue.status, Issue.Status.VALIDATED)

        # 3. VALIDATED -> AVAILABLE_FOR_ADOPTION
        issue.transition_status(Issue.Status.AVAILABLE_FOR_ADOPTION, actor=self.admin, reason="Published on state civic challenge portal.")
        self.assertEqual(issue.status, Issue.Status.AVAILABLE_FOR_ADOPTION)

        # 4. AVAILABLE_FOR_ADOPTION -> ADOPTION_REQUESTED
        issue.transition_status(Issue.Status.ADOPTION_REQUESTED, actor=self.coordinator, reason="BIT Sindri coordinator submitted adoption request.")
        self.assertEqual(issue.status, Issue.Status.ADOPTION_REQUESTED)

        # 5. ADOPTION_REQUESTED -> ADOPTED
        issue.transition_status(Issue.Status.ADOPTED, actor=self.coordinator, reason="Adoption approved and repository initialized.")
        self.assertEqual(issue.status, Issue.Status.ADOPTED)

        # 6. ADOPTED -> OPEN
        issue.transition_status(Issue.Status.OPEN, actor=self.coordinator, reason="Open Call announced for student teams.")
        self.assertEqual(issue.status, Issue.Status.OPEN)

        # 7. OPEN -> UNDER_REVIEW
        issue.transition_status(Issue.Status.UNDER_REVIEW, actor=self.coordinator, reason="Open Call closed; University Review Board in session.")
        self.assertEqual(issue.status, Issue.Status.UNDER_REVIEW)

        # 8. UNDER_REVIEW -> SOLUTION_SELECTED
        issue.transition_status(Issue.Status.SOLUTION_SELECTED, actor=self.coordinator, reason="Winning student proposal selected by review board.")
        self.assertEqual(issue.status, Issue.Status.SOLUTION_SELECTED)

        # 9. SOLUTION_SELECTED -> PROJECT
        issue.transition_status(Issue.Status.PROJECT, actor=self.coordinator, reason="Implementation project created with assigned faculty mentor.")
        self.assertEqual(issue.status, Issue.Status.PROJECT)

        # 10. PROJECT -> PROTOTYPE
        issue.transition_status(Issue.Status.PROTOTYPE, actor=self.mentor, reason="Laboratory prototype fabrication under active development.")
        self.assertEqual(issue.status, Issue.Status.PROTOTYPE)

        # 11. PROTOTYPE -> PILOT
        issue.transition_status(Issue.Status.PILOT, actor=self.mentor, reason="Field pilot installed at target school.")
        self.assertEqual(issue.status, Issue.Status.PILOT)

        # 12. PILOT -> DEPLOYED
        issue.transition_status(Issue.Status.DEPLOYED, actor=self.mentor, reason="Field deployment fully operational.")
        self.assertEqual(issue.status, Issue.Status.DEPLOYED)

        # 13. DEPLOYED -> AWAITING_CITIZEN_VERIFICATION
        issue.transition_status(Issue.Status.AWAITING_CITIZEN_VERIFICATION, actor=self.admin, reason="Dispatched verification alert to reporting citizen.")
        self.assertEqual(issue.status, Issue.Status.AWAITING_CITIZEN_VERIFICATION)

        # 14. AWAITING_CITIZEN_VERIFICATION -> RESOLVED
        issue.transition_status(Issue.Status.RESOLVED, actor=self.citizen, reason="Citizen confirmed clean drinking water running daily.")
        self.assertEqual(issue.status, Issue.Status.RESOLVED)

        # Verify audit history tracked all 14 state changes
        history = issue.status_history.all()
        self.assertEqual(history.count(), 14)
