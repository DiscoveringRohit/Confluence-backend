from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    CustomTokenObtainPairView,
    UserProfileView,
    UniversityListView,
    OrganizationListView,
    UserListView,
    UniversityStudentsListView,
    UniversityMentorsListView,
    UniversityCoordinatorsListView,
    UserDetailView,
)

auth_urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='auth_login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='auth_token_refresh'),
    path('profile/', UserProfileView.as_view(), name='auth_profile'),
    path('universities/', UniversityListView.as_view(), name='auth_universities'),
    path('organizations/', OrganizationListView.as_view(), name='auth_organizations'),
]

user_urlpatterns = [
    path('', UserListView.as_view(), name='user_list'),
    path('<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('universities/', UniversityListView.as_view(), name='university_list'),
    path('universities/<int:university_id>/students/', UniversityStudentsListView.as_view(), name='university_students'),
    path('universities/<int:university_id>/mentors/', UniversityMentorsListView.as_view(), name='university_mentors'),
    path('universities/<int:university_id>/coordinators/', UniversityCoordinatorsListView.as_view(), name='university_coordinators'),
    path('organizations/', OrganizationListView.as_view(), name='organization_list'),
]

urlpatterns = auth_urlpatterns + user_urlpatterns


