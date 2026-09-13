from django.urls import path
from .views import GovAnalyticsSummaryView

urlpatterns = [
    path('summary/', GovAnalyticsSummaryView.as_view(), name='gov_analytics_summary'),
]
