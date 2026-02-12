"""Permission classes for analytics endpoints.

Ensures users can only access analytics if authenticated.
Access control is handled at the view level using Child.for_user().
"""

from rest_framework.permissions import IsAuthenticated


class HasAnalyticsAccess(IsAuthenticated):
    """Check if user is authenticated for analytics access.

    Child access control is handled in the view layer using Child.for_user(),
    which returns a 404 if the user doesn't have access to the child.
    This maintains security through obscurity consistent with the existing model.
    """

    pass
