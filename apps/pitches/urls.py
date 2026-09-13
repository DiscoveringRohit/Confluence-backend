from django.urls import path
from .views import (
    PitchListCreateView,
    PitchDetailView,
    CommunityFeedbackCreateView,
    ScoreFeedbackView,
    ReviewBoardActionView,
    UpdateMilestonesView,
)

urlpatterns = [
    path('', PitchListCreateView.as_view(), name='pitch_list_create'),
    path('<int:pk>/', PitchDetailView.as_view(), name='pitch_detail'),
    path('<int:pitch_id>/feedback/', CommunityFeedbackCreateView.as_view(), name='community_feedback_create'),
    path('feedback/<int:pk>/score/', ScoreFeedbackView.as_view(), name='score_feedback'),
    path('<int:pk>/review-action/', ReviewBoardActionView.as_view(), name='pitch_review_action'),
    path('lifecycle/<int:pk>/update/', UpdateMilestonesView.as_view(), name='update_milestones'),
]
