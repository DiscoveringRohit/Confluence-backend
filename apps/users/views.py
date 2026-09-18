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
    AdminUserSerializer,
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

    def perform_create(self, serializer):
        user = self.request.user
        is_admin = user.is_authenticated and (user.is_staff or user.is_superuser or getattr(user, 'role', None) in [User.Role.GOV_ADMIN, User.Role.ADMIN, 'admin'])
        if not is_admin:
            raise PermissionDenied("Only administrators can create universities.")
        serializer.save()


class OrganizationListView(generics.ListCreateAPIView):
    queryset = Organization.objects.all().order_by('name')
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        user = self.request.user
        is_admin = user.is_authenticated and (user.is_staff or user.is_superuser or getattr(user, 'role', None) in [User.Role.GOV_ADMIN, User.Role.ADMIN, 'admin'])
        if not is_admin:
            raise PermissionDenied("Only administrators can create organizations.")
        serializer.save()


class UserListView(generics.ListCreateAPIView):
    """
    User directory and admin user management.
    - Admins and Government Administrators: Full access with AdminUserSerializer, creation of any stakeholder role, and comprehensive filtering.
    - Other Authenticated Users: Safe directory access with DirectoryUserSerializer.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', None) in [User.Role.GOV_ADMIN, User.Role.ADMIN, 'admin']
        if is_admin:
            return AdminUserSerializer
        return DirectoryUserSerializer

    def get_queryset(self):
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', None) in [User.Role.GOV_ADMIN, User.Role.ADMIN, 'admin']
        is_coord = getattr(user, 'role', None) == User.Role.UNIVERSITY_COORDINATOR

        qs = User.objects.select_related('university', 'organization').all().order_by('id')

        if not is_admin:
            if is_coord and user.university_id:
                qs = qs.filter(university_id=user.university_id)
            elif user.university_id:
                qs = qs.filter(university_id=user.university_id)

        role = self.request.query_params.get('role')
        if role and role != 'all':
            qs = qs.filter(role=role)
        university_id = self.request.query_params.get('university')
        if university_id:
            qs = qs.filter(university_id=university_id)
        org_id = self.request.query_params.get('organization')
        if org_id:
            qs = qs.filter(organization_id=org_id)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ['true', '1'])
        search = self.request.query_params.get('search')
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search))
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', None) in [User.Role.GOV_ADMIN, User.Role.ADMIN, 'admin']
        if not is_admin:
            raise PermissionDenied("Only administrators can create users directly.")
        password = self.request.data.get('password', 'Password@123')
        instance = serializer.save()
        instance.set_password(password or 'Password@123')
        if self.request.data.get('is_superuser'):
            instance.is_superuser = True
        if self.request.data.get('is_staff'):
            instance.is_staff = True
        if 'is_active' in self.request.data:
            instance.is_active = bool(self.request.data['is_active'])
        instance.save()


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


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a user account by primary key (M-06).
    - Platform Admins / Superusers: Unrestricted authority to inspect, update any attribute, or delete any account.
    - Users: Can view and update their own profile.
    - University Coordinators: Can view profiles of users affiliated with their university.
    """
    permission_classes = [permissions.IsAuthenticated]
    queryset = User.objects.select_related('university', 'organization').all()

    def get_serializer_class(self):
        user = self.request.user
        target_user_id = self.kwargs.get('pk')
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', None) in [User.Role.GOV_ADMIN, User.Role.ADMIN, 'admin']
        if is_admin or user.id == int(target_user_id):
            return UserProfileSerializer
        return DirectoryUserSerializer

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        user = request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', None) in [User.Role.GOV_ADMIN, User.Role.ADMIN, 'admin']
        if is_admin:
            return
        if user.id == obj.id:
            return
        if getattr(user, 'role', None) == User.Role.UNIVERSITY_COORDINATOR and user.university_id and user.university_id == obj.university_id:
            if request.method in permissions.SAFE_METHODS:
                return
        raise PermissionDenied("You do not have permission to view or modify this user account.")

    def perform_update(self, serializer):
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser or getattr(user, 'role', None) in [User.Role.GOV_ADMIN, User.Role.ADMIN, 'admin']
        instance = serializer.save()
        if is_admin:
            data = self.request.data
            if 'password' in data and data['password']:
                instance.set_password(data['password'])
            if 'is_superuser' in data:
                instance.is_superuser = bool(data['is_superuser'])
            if 'is_staff' in data:
                instance.is_staff = bool(data['is_staff'])
            if 'is_active' in data:
                instance.is_active = bool(data['is_active'])
            instance.save()


class UniversityDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete an accredited university."""
    queryset = University.objects.all()
    serializer_class = UniversitySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class OrganizationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete an industry / CSR organization."""
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]



