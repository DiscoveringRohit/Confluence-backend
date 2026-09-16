from rest_framework import permissions


class CanUpdateIssue(permissions.BasePermission):
    """
    Object-level permission for issues:
    - SAFE_METHODS (GET, HEAD, OPTIONS): allowed for anyone.
    - Updates (PUT, PATCH):
      * Citizen (creator) can edit their own issue ONLY while it is in SUBMITTED state.
      * University coordinator can edit if their university has adopted the issue.
      * Gov admin or staff can edit any issue.
      * All other users are denied.
    - Delete:
      * Gov admin, staff, or creator while in SUBMITTED state.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.is_staff or getattr(user, 'role', None) == 'gov_admin':
            return True

        # Citizen (creator) can edit their own challenge while in SUBMITTED or REOPENED state (Issue 47)
        if obj.submitted_by_id == user.id:
            return obj.status in [obj.Status.SUBMITTED, obj.Status.REOPENED]

        # University coordinator of the adopting/maintaining university can update metadata
        if getattr(user, 'role', None) == 'university_coordinator' and user.university_id:
            is_maintaining = (
                obj.maintaining_university_id == user.university_id or
                (hasattr(obj, 'adoption') and obj.adoption and obj.adoption.university_id == user.university_id)
            )
            if is_maintaining:
                return True

        return False
