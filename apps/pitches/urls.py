from django.urls import path
from .views import (
    PitchListCreateView,
    PitchDetailView,
    CommunityFeedbackCreateView,
    ScoreFeedbackView,
    ReviewBoardActionView,
    UpdateMilestonesView,
    ResubmitPitchView,
    SolutionEvaluationListCreateView,
    SolutionEvaluationDetailView,
    SolutionTeamMemberView,
    PitchDiscussionListCreateView,
    ReviewSessionListCreateView,
    ReviewSessionDetailView,
    ProjectListCreateView,
    ProjectDetailView,
    ProjectMilestoneListCreateView,
    ProjectMilestoneDetailView,
    ProjectMilestoneReviewView,
    ProjectSubmitDeploymentView,
    ProjectApproveDeploymentView,
    ProjectDiscussionListCreateView,
    ProjectStatusHistoryView,
    ProjectExpressInterestView,
    ProjectIndustryEngagementListView,
    GenerateCertificateView,
    VerifyCertificateView,
    UserCertificateListView,
    ProjectMemberView,
)

urlpatterns = [
    path('', PitchListCreateView.as_view(), name='pitch_list_create'),
    # Issue 31: Review Sessions
    path('review-sessions/', ReviewSessionListCreateView.as_view(), name='review_sessions_list_create'),
    path('review-sessions/<int:pk>/', ReviewSessionDetailView.as_view(), name='review_session_detail'),
    # Issue 32 & 33: Projects
    path('projects/', ProjectListCreateView.as_view(), name='projects_list_create'),
    path('projects/<str:pk>/', ProjectDetailView.as_view(), name='project_detail'),
    # Project Team
    path('projects/<str:project_id>/team/', ProjectMemberView.as_view(), name='project_team'),
    path('projects/<str:project_id>/team/<int:member_id>/', ProjectMemberView.as_view(), name='project_team_detail'),
    path('projects/<str:project_id>/members/', ProjectMemberView.as_view(), name='project_members_alias'),
    path('projects/<str:project_id>/members/<int:member_id>/', ProjectMemberView.as_view(), name='project_members_detail_alias'),
    # Issue 34: Project Milestones
    path('projects/<str:project_id>/milestones/', ProjectMilestoneListCreateView.as_view(), name='project_milestones_list_create'),
    path('projects/<str:project_id>/milestones/<int:pk>/', ProjectMilestoneDetailView.as_view(), name='project_milestone_detail'),
    path('projects/<str:project_id>/milestones/<int:pk>/review/', ProjectMilestoneReviewView.as_view(), name='project_milestone_review'),
    path('milestones/<int:pk>/', ProjectMilestoneDetailView.as_view(), name='milestone_detail_global'),
    path('milestones/<int:pk>/review/', ProjectMilestoneReviewView.as_view(), name='milestone_review_global'),
    # Issue 35: Deployment Gate
    path('projects/<str:pk>/submit-deployment/', ProjectSubmitDeploymentView.as_view(), name='project_submit_deployment'),
    path('projects/<str:pk>/approve-deployment/', ProjectApproveDeploymentView.as_view(), name='project_approve_deployment'),
    # Issue 39 & 40: Project Status History & Discussions
    path('projects/<str:project_id>/discussions/', ProjectDiscussionListCreateView.as_view(), name='project_discussions'),
    path('projects/<str:pk>/status-history/', ProjectStatusHistoryView.as_view(), name='project_status_history'),
    # Issue 51: Project-Scoped Industry Workflow
    path('projects/<str:project_id>/express-interest/', ProjectExpressInterestView.as_view(), name='project_express_interest'),
    path('projects/<str:project_id>/engagements/', ProjectIndustryEngagementListView.as_view(), name='project_engagements'),
    # Issue 55: Verified Outcome Certificates
    path('certificates/', UserCertificateListView.as_view(), name='user_certificates'),
    path('certificates/mine/', UserCertificateListView.as_view(), name='user_certificates_mine'),
    path('projects/<str:project_id>/certificates/generate/', GenerateCertificateView.as_view(), name='project_generate_certificates'),
    path('certificates/<str:certificate_id>/verify/', VerifyCertificateView.as_view(), name='verify_certificate'),
    # Solution Evaluations, Feedback & Lifecycle
    path('evaluations/<int:pk>/', SolutionEvaluationDetailView.as_view(), name='solution_evaluation_detail'),
    path('feedback/<int:pk>/score/', ScoreFeedbackView.as_view(), name='score_feedback'),
    path('lifecycle/<int:pk>/update/', UpdateMilestonesView.as_view(), name='update_milestones'),
    # Pitches / Solutions sub-routes (must precede <str:pk>/)
    path('<str:pitch_id>/team/', SolutionTeamMemberView.as_view(), name='solution_team'),
    path('<str:pitch_id>/team/<int:member_id>/', SolutionTeamMemberView.as_view(), name='solution_team_detail'),
    path('<str:pitch_id>/discussions/', PitchDiscussionListCreateView.as_view(), name='solution_discussions'),
    path('<str:pitch_id>/feedback/', CommunityFeedbackCreateView.as_view(), name='community_feedback_create'),
    path('<str:pitch_id>/evaluations/', SolutionEvaluationListCreateView.as_view(), name='solution_evaluations'),
    path('<str:pk>/action/', ReviewBoardActionView.as_view(), name='pitch_action_alias'),
    path('<str:pk>/review-action/', ReviewBoardActionView.as_view(), name='pitch_review_action'),
    path('<str:pk>/review_action/', ReviewBoardActionView.as_view(), name='pitch_review_action_alias'),
    path('<str:pk>/resubmit/', ResubmitPitchView.as_view(), name='pitch_resubmit'),
    path('<str:pk>/', PitchDetailView.as_view(), name='pitch_detail'),
]

