from django.urls import path
from .views import (
    IssueListCreateView,
    IssueDetailView,
    IssueModerationView,
    AdoptIssueView,
    NominateIssueView,
    ReviewNominationView,
    UniversityNominationsListView,
    CitizenConfirmResolutionView,
)

urlpatterns = [
    path('', IssueListCreateView.as_view(), name='issue_list_create'),
    path('<int:pk>/', IssueDetailView.as_view(), name='issue_detail'),
    path('<int:pk>/moderate/', IssueModerationView.as_view(), name='issue_moderate'),
    path('<int:pk>/adopt/', AdoptIssueView.as_view(), name='issue_adopt'),
    path('<int:pk>/nominate/', NominateIssueView.as_view(), name='issue_nominate'),
    path('nominations/', UniversityNominationsListView.as_view(), name='university_nominations'),
    path('nominations/<int:pk>/review/', ReviewNominationView.as_view(), name='review_nomination'),
    path('<int:pk>/confirm-resolution/', CitizenConfirmResolutionView.as_view(), name='citizen_confirm_resolution'),
]
