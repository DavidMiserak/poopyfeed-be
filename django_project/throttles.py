"""Custom DRF throttle classes for rate limiting API endpoints."""

from rest_framework.throttling import UserRateThrottle


class AcceptInviteThrottle(UserRateThrottle):
    """Stricter rate limiting for invite acceptance operations.

    The accept_invite endpoint involves database transactions and race condition
    handling. Stricter limits prevent abuse and reduce transaction contention.

    Rate: 20 requests per hour per user (one per 3 minutes)
    """

    scope = "accept_invite"


class TrackingCreateThrottle(UserRateThrottle):
    """Stricter rate limiting for tracking record creation operations.

    Prevents rapid mass-insertion of tracking records (feedings, diapers, naps).
    Rate: 120 requests per hour per user (one per 30 seconds)
    """

    scope = "tracking_create"
