from django.urls import path
from .views import (
    IndustryEngagementListCreateView,
    RespondEngagementView,
)

urlpatterns = [
    path('', IndustryEngagementListCreateView.as_view(), name='engagement_list_create'),
    path('<int:pk>/respond/', RespondEngagementView.as_view(), name='respond_engagement'),
]
