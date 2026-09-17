from rest_framework import permissions


class ProjectAccessPermission(permissions.BasePermission):
    """
    Object-level authorization for Project resources (C-02):
    - Read (GET, HEAD, OPTIONS):
        * Staff / Government Admin
        * University Coordinator of the project's university
        * Faculty Mentor of the project's university or assigned mentor
        * Student innovators who are members of the project team
        * Citizen who submitted the underlying challenge/issue
        * Industry Partner whose organization is engaged with the project
        * Denied for unrelated students, citizens, and external parties.
    - Write (PATCH, PUT, DELETE):
        * Staff / Government Admin
        * University Coordinator of the project's university
        * Assigned Mentor (only for non-workflow fields like target_date/notes)
        * Denied for students, citizens, industry partners, and unrelated users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.is_staff or getattr(user, 'role', None) == 'gov_admin':
            return True

        # Check Read Access
        if request.method in permissions.SAFE_METHODS:
            # University Coordinator / Faculty Mentor of the university
            if getattr(user, 'role', None) in ['university_coordinator', 'faculty_mentor']:
                if user.university_id and user.university_id == obj.university_id:
                    return True
                if obj.mentor_id == user.id:
                    return True

            # Student team member
            if getattr(user, 'role', None) == 'student':
                if obj.team.filter(id=user.id).exists():
                    return True

            # Citizen reporter of the underlying challenge
            if getattr(user, 'role', None) == 'citizen':
                if obj.challenge and obj.challenge.submitted_by_id == user.id:
                    return True

            # Industry partner with engagement
            if getattr(user, 'role', None) == 'industry_partner' and user.organization_id:
                if hasattr(obj, 'industry_engagements') and obj.industry_engagements.filter(industry_org_id=user.organization_id).exists():
                    return True

            return False

        # Check Write Access (PATCH, PUT, DELETE)
        # University coordinator of this project's university
        if getattr(user, 'role', None) == 'university_coordinator':
            return bool(user.university_id and user.university_id == obj.university_id)

        # Assigned mentor can update project details (non-workflow fields)
        if getattr(user, 'role', None) == 'faculty_mentor':
            return bool(obj.mentor_id == user.id)

        # Students and citizens cannot directly mutate the project container
        return False
