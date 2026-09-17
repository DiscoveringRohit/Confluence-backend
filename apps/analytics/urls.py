from django.urls import path
from .views import GovAnalyticsSummaryView, InstitutionalAnalyticsView

urlpatterns = [
    path('summary/', GovAnalyticsSummaryView.as_view(), name='gov_analytics_summary'),
    path('gov/summary/', GovAnalyticsSummaryView.as_view(), name='gov_analytics_summary_alias'),
    path('institutional/', InstitutionalAnalyticsView.as_view(), name='institutional_analytics'),
    path('gov/institutional/', InstitutionalAnalyticsView.as_view(), name='institutional_analytics_alias'),
]
