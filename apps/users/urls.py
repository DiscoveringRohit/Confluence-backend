from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    CustomTokenObtainPairView,
    UserProfileView,
    UniversityListView,
    OrganizationListView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='auth_login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='auth_token_refresh'),
    path('profile/', UserProfileView.as_view(), name='auth_profile'),
    path('universities/', UniversityListView.as_view(), name='university_list'),
    path('organizations/', OrganizationListView.as_view(), name='organization_list'),
]
