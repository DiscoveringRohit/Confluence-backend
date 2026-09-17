from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, University, Organization
from .serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
    DirectoryUserSerializer,
    UniversitySerializer,
    OrganizationSerializer,
)

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'name': self.user.name,
            'role': self.user.role,
            'university_id': self.user.university_id,
            'organization_id': self.user.organization_id,
        }
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UniversityListView(generics.ListCreateAPIView):
    queryset = University.objects.all().order_by('name')
    serializer_class = UniversitySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class OrganizationListView(generics.ListCreateAPIView):
    queryset = Organization.objects.all().order_by('name')
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class UserListView(generics.ListAPIView):
    """
    Restricted user directory (M-01).
    - Admins and Government Administrators: Can query all users across the platform.
    - University Coordinators: Can query users affiliated with their own university.
    - External/Student/Citizen accounts: Denied access to prevent user enumeration and data scraping.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        user = self.request.user
        if user.is_staff or getattr(user, 'role', None) == User.Role.GOV_ADMIN:
            return UserProfileSerializer
        return DirectoryUserSerializer

    def get_queryset(self):
        user = self.request.user
        is_admin = user.is_staff or getattr(user, 'role', None) == User.Role.GOV_ADMIN
        is_coord = getattr(user, 'role', None) == User.Role.UNIVERSITY_COORDINATOR

        if not (is_admin or is_coord):
            raise PermissionDenied("Access to the global user directory is restricted.")

        qs = User.objects.select_related('university', 'organization').all().order_by('id')
        if is_coord and not is_admin:
            if not user.university_id:
                raise PermissionDenied("Coordinator must be associated with an active university.")
            qs = qs.filter(university_id=user.university_id)

        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)
        university_id = self.request.query_params.get('university')
        if university_id and is_admin:
            qs = qs.filter(university_id=university_id)
        return qs


class UniversityStudentsListView(generics.ListAPIView):
    """
    Lists students affiliated with a specific university (M-01 & M-04).
    Accessible by:
    - Same university students, mentors, coordinators
    - Platform administrators and government officials
    Uses DirectoryUserSerializer to prevent PII exposure (omits phone numbers).
    """
    serializer_class = DirectoryUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        univ_id = self.kwargs['university_id']
        is_admin = user.is_staff or getattr(user, 'role', None) == User.Role.GOV_ADMIN
        is_same_univ = (user.university_id is not None and user.university_id == int(univ_id))

        if not (is_admin or is_same_univ):
            raise PermissionDenied("You may only view student rosters from your own university.")

        return User.objects.select_related('university').filter(
            role=User.Role.STUDENT,
            university_id=univ_id
        ).order_by('name')


class UniversityMentorsListView(generics.ListAPIView):
    """
    Lists mentors affiliated with a specific university.
    Accessible by users from the same university or platform administrators.
    """
    serializer_class = DirectoryUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        univ_id = self.kwargs['university_id']
        is_admin = user.is_staff or getattr(user, 'role', None) == User.Role.GOV_ADMIN
        is_same_univ = (user.university_id is not None and user.university_id == int(univ_id))

        if not (is_admin or is_same_univ):
            raise PermissionDenied("You may only view faculty mentors from your own university.")

        return User.objects.select_related('university').filter(
            role=User.Role.FACULTY_MENTOR,
            university_id=univ_id
        ).order_by('name')


class UniversityCoordinatorsListView(generics.ListAPIView):
    """
    Lists coordinators affiliated with a specific university.
    """
    serializer_class = DirectoryUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        univ_id = self.kwargs['university_id']
        is_admin = user.is_staff or getattr(user, 'role', None) == User.Role.GOV_ADMIN
        is_same_univ = (user.university_id is not None and user.university_id == int(univ_id))

        if not (is_admin or is_same_univ):
            raise PermissionDenied("You may only view coordinators from your own university.")

        return User.objects.select_related('university').filter(
            role=User.Role.UNIVERSITY_COORDINATOR,
            university_id=univ_id
        ).order_by('name')


class UserDetailView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update a user account by primary key (M-06).
    - Users can view and update their own profile.
    - Staff / Gov Admins can view any user profile.
    - University Coordinators can view profiles of users affiliated with their university.
    """
    permission_classes = [permissions.IsAuthenticated]
    queryset = User.objects.select_related('university', 'organization').all()

    def get_serializer_class(self):
        user = self.request.user
        target_user_id = self.kwargs.get('pk')
        if user.is_staff or getattr(user, 'role', None) == User.Role.GOV_ADMIN or user.id == int(target_user_id):
            return UserProfileSerializer
        return DirectoryUserSerializer

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        user = request.user
        if user.is_staff or getattr(user, 'role', None) == User.Role.GOV_ADMIN:
            return
        if user.id == obj.id:
            return
        if getattr(user, 'role', None) == User.Role.UNIVERSITY_COORDINATOR and user.university_id and user.university_id == obj.university_id:
            if request.method in permissions.SAFE_METHODS:
                return
        raise PermissionDenied("You do not have permission to view or modify this user account.")


