from rest_framework import permissions

class IsCitizen(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'citizen')

class IsStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'student')

class IsUniversityCoordinator(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'university_coordinator')

class IsFacultyMentor(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'faculty_mentor')

class IsUniversityAffiliated(permissions.BasePermission):
    """Allows University Coordinator or Faculty Mentor."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and 
            request.user.role in ['university_coordinator', 'faculty_mentor']
        )

class IsIndustryPartner(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'industry_partner')

class IsGovAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.role == 'gov_admin' or request.user.is_staff))
