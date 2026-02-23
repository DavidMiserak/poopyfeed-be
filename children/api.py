"""REST API for children app: Child, ChildShare, ShareInvite."""

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from django_project.throttles import AcceptInviteThrottle

from .api_permissions import CanEditChild, CanManageSharing, HasChildAccess
from .models import Child, ChildShare, ShareInvite

# --- Serializers ---


class ChildSerializer(serializers.ModelSerializer):
    """Child serializer with computed permission fields.

    Optimized to avoid N+1 queries by using prefetched shares instead of
    calling model methods that would re-query the database.
    Requires: get_queryset() must include .prefetch_related("shares__user")
    """

    user_role = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_manage_sharing = serializers.SerializerMethodField()
    last_diaper_change = serializers.DateTimeField(read_only=True, allow_null=True)
    last_nap = serializers.DateTimeField(read_only=True, allow_null=True)
    last_feeding = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = Child
        fields = [
            "id",
            "name",
            "date_of_birth",
            "gender",
            "custom_bottle_low_oz",
            "custom_bottle_mid_oz",
            "custom_bottle_high_oz",
            "created_at",
            "updated_at",
            "user_role",
            "can_edit",
            "can_manage_sharing",
            "last_diaper_change",
            "last_nap",
            "last_feeding",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def _get_user_share(self, obj, user):
        """Find user's share in prefetched shares (avoids database query).

        Loops through obj.shares.all() which uses prefetched data when available,
        falling back to database query only if shares weren't prefetched.
        """
        user_id = user.id
        for share in obj.shares.all():
            if share.user_id == user_id:
                return share
        return None

    def get_user_role(self, obj):
        """Get user's role using prefetched share data.

        Returns 'owner', 'co-parent', 'caregiver', or None.
        Uses prefetched shares to avoid N+1 queries in list views.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        # Check if user is owner (fast, no query)
        if obj.parent_id == request.user.id:
            return "owner"

        # Use prefetched shares instead of calling obj.get_user_role()
        share = self._get_user_share(obj, request.user)
        if share:
            role_map = {
                ChildShare.Role.CO_PARENT: "co-parent",
                ChildShare.Role.CAREGIVER: "caregiver",
            }
            return role_map.get(share.role)

        return None

    def get_can_edit(self, obj):
        """Check if user can edit child or tracking records.

        Uses prefetched share data to avoid queries.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        # Get user_role without querying the database
        user_role = self.get_user_role(obj)
        return user_role in ["owner", "co-parent"]

    def get_can_manage_sharing(self, obj):
        """Check if user can manage sharing (owner only).

        This is always fast (no shares.filter() needed).
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        return obj.parent_id == request.user.id

    def validate_custom_bottle_low_oz(self, value):
        """Validate custom bottle low amount is in range 0.1-50 oz."""
        if value is not None and (value < 0.1 or value > 50):
            raise serializers.ValidationError(
                "Custom bottle low amount must be between 0.1 and 50 oz."
            )
        return value

    def validate_custom_bottle_mid_oz(self, value):
        """Validate custom bottle mid amount is in range 0.1-50 oz."""
        if value is not None and (value < 0.1 or value > 50):
            raise serializers.ValidationError(
                "Custom bottle mid amount must be between 0.1 and 50 oz."
            )
        return value

    def validate_custom_bottle_high_oz(self, value):
        """Validate custom bottle high amount is in range 0.1-50 oz."""
        if value is not None and (value < 0.1 or value > 50):
            raise serializers.ValidationError(
                "Custom bottle high amount must be between 0.1 and 50 oz."
            )
        return value

    def validate(self, data):
        """Validate custom bottle amounts: all set or all null.

        Rules:
        - All three null (use age-based defaults) ✓
        - All three set with low < mid < high ✓
        - Any combination of partial nulls ✗
        - Any out-of-order values ✗

        Prevents scenarios like: low=10, mid=null, high=5
        which would become: 10 < age_default < 5 (invalid).
        """
        low = data.get("custom_bottle_low_oz")
        mid = data.get("custom_bottle_mid_oz")
        high = data.get("custom_bottle_high_oz")

        # All null is valid (use age-based defaults)
        if low is None and mid is None and high is None:
            return data

        # Count how many fields are set
        set_count = sum(1 for v in [low, mid, high] if v is not None)

        # If only some are set, require all to be set
        if set_count > 0 and set_count < 3:
            raise serializers.ValidationError(
                "If setting custom amounts, all three (low, recommended, high) "
                "must be provided. Leave all blank to use age-based defaults."
            )

        # All three are set - validate ordering
        if set_count == 3:
            if low >= mid:
                raise serializers.ValidationError(
                    "Low amount must be less than recommended amount."
                )

            if mid >= high:
                raise serializers.ValidationError(
                    "Recommended amount must be less than high amount."
                )

            if low >= high:
                raise serializers.ValidationError(
                    "Low amount must be less than high amount."
                )

        return data


class ChildShareSerializer(serializers.ModelSerializer):
    """ChildShare serializer with user email."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = ChildShare
        fields = [
            "id",
            "user_email",
            "role",
            "role_display",
            "created_at",
        ]
        read_only_fields = ["id", "user_email", "role_display", "created_at"]

    def get_role(self, obj):
        """Return full role string for frontend compatibility."""
        role_map = {
            ChildShare.Role.CO_PARENT: "co-parent",
            ChildShare.Role.CAREGIVER: "caregiver",
        }
        return role_map.get(obj.role)


class ShareInviteSerializer(serializers.ModelSerializer):
    """ShareInvite serializer with invite URL."""

    role = serializers.CharField()
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    invite_url = serializers.SerializerMethodField()

    class Meta:
        model = ShareInvite
        fields = [
            "id",
            "token",
            "role",
            "role_display",
            "is_active",
            "created_at",
            "invite_url",
        ]
        read_only_fields = ["id", "token", "role_display", "created_at", "invite_url"]

    def validate_role(self, value):
        """Validate and transform role from API format to database format."""
        role_map = {
            "co-parent": ChildShare.Role.CO_PARENT,
            "caregiver": ChildShare.Role.CAREGIVER,
        }
        if value not in role_map:
            raise serializers.ValidationError(
                f"Invalid role. Must be 'co-parent' or 'caregiver'."
            )
        return role_map[value]

    def to_representation(self, instance):
        """Transform role from database format to API format."""
        data = super().to_representation(instance)
        role_map = {
            ChildShare.Role.CO_PARENT: "co-parent",
            ChildShare.Role.CAREGIVER: "caregiver",
        }
        data["role"] = role_map.get(instance.role)
        return data

    def get_invite_url(self, obj):
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(f"/children/accept-invite/{obj.token}/")
        return None


class AcceptInviteSerializer(serializers.Serializer):
    """Serializer for accepting an invite by token."""

    token = serializers.CharField(max_length=64)

    def validate_token(self, value):
        try:
            invite = ShareInvite.objects.get(token=value, is_active=True)
        except ShareInvite.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive invite token.")
        self.invite = invite
        return value


# --- ViewSets ---


class ChildViewSet(viewsets.ModelViewSet):
    """ViewSet for Child CRUD operations.

    Uses cached last-activity annotations to avoid expensive database aggregations.
    Cache is automatically invalidated when tracking records are created/updated/deleted.
    """

    serializer_class = ChildSerializer
    permission_classes = [IsAuthenticated, HasChildAccess]

    def get_queryset(self):
        """Return children accessible to the current user without annotations.

        Annotations are applied via _apply_cached_annotations() method to use
        cached values instead of expensive database aggregations.
        """
        return (
            Child.for_user(self.request.user)
            .select_related("parent")
            .prefetch_related("shares__user")
            .order_by("-date_of_birth")
        )

    def _apply_cached_annotations(self, children):
        """Apply cached last-activity annotations to child objects.

        This method is called after the queryset is evaluated (and paginated)
        to apply cached annotation values instead of using database aggregations.
        This avoids the expensive Max() queries on every request.

        Args:
            children: List of Child objects from paginated queryset

        Returns:
            Same list with last_diaper_change, last_nap, last_feeding attached
        """
        from .cache_utils import get_child_last_activities

        if not children:
            return children

        child_ids = [child.id for child in children]
        activities = get_child_last_activities(child_ids)

        # Attach cached annotation values to each child
        for child in children:
            activity = activities.get(child.id, {})
            child.last_diaper_change = activity.get("last_diaper_change")
            child.last_nap = activity.get("last_nap")
            child.last_feeding = activity.get("last_feeding")

        return children

    def list(self, request, *args, **kwargs):
        """List children with cached annotations applied before serialization."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            # Apply cached annotations to paginated results before serialization
            page = self._apply_cached_annotations(page)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Non-paginated response (shouldn't happen with default pagination)
        queryset = list(queryset)
        queryset = self._apply_cached_annotations(queryset)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve single child with cached annotations."""
        instance = self.get_object()
        # Apply cached annotations for single object
        instance = self._apply_cached_annotations([instance])[0]
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def get_permissions(self):
        """Apply different permissions based on action."""
        if self.action in ["update", "partial_update"]:
            return [IsAuthenticated(), CanEditChild()]
        elif self.action == "destroy":
            return [IsAuthenticated(), CanManageSharing()]
        return super().get_permissions()

    def perform_create(self, serializer):
        """Set parent to current user when creating a child."""
        serializer.save(parent=self.request.user)

    # --- Sharing actions ---

    @action(detail=True, methods=["get"], permission_classes=[CanManageSharing])
    def shares(self, request, pk=None):
        """List all shares for a child (owner only)."""
        child = self.get_object()
        shares = child.shares.select_related("user")
        serializer = ChildShareSerializer(
            shares, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["delete"],
        url_path="shares/(?P<share_pk>[^/.]+)",
        permission_classes=[CanManageSharing],
    )
    def revoke_share(self, request, pk=None, share_pk=None):
        """Revoke a user's access to child (owner only)."""
        child = self.get_object()
        share = get_object_or_404(ChildShare, pk=share_pk, child=child)
        share.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], permission_classes=[CanManageSharing])
    def invites(self, request, pk=None):
        """List or create invites for a child (owner only)."""
        child = self.get_object()

        if request.method == "GET":
            invites = child.invites.select_related("created_by")
            serializer = ShareInviteSerializer(
                invites, many=True, context={"request": request}
            )
            return Response(serializer.data)

        # POST - create invite
        serializer = ShareInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(child=child, created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch"],
        url_path="invites/(?P<invite_pk>[^/.]+)",
        permission_classes=[CanManageSharing],
    )
    def toggle_invite(self, request, pk=None, invite_pk=None):
        """Toggle invite active status (owner only)."""
        child = self.get_object()
        invite = get_object_or_404(ShareInvite, pk=invite_pk, child=child)
        invite.is_active = not invite.is_active
        invite.save()
        serializer = ShareInviteSerializer(invite, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["delete"],
        url_path="invites/(?P<invite_pk>[^/.]+)/delete",
        permission_classes=[CanManageSharing],
    )
    def delete_invite(self, request, pk=None, invite_pk=None):
        """Delete an invite (owner only)."""
        child = self.get_object()
        invite = get_object_or_404(ShareInvite, pk=invite_pk, child=child)
        invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AcceptInviteViewSet(viewsets.ViewSet):
    """ViewSet for accepting invites.

    Stricter rate limiting (20/hour) applied due to database transactions
    and race condition handling in the accept action.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [AcceptInviteThrottle]

    @action(detail=False, methods=["post"])
    def accept(self, request):
        """Accept an invite by token."""
        serializer = AcceptInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invite = serializer.invite

        # Check if user is already the owner
        if invite.child.parent == request.user:
            return Response(
                {"error": "You are already the owner of this child."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Handle potential race condition with get_or_create
        with transaction.atomic():
            try:
                share, created = ChildShare.objects.get_or_create(
                    child=invite.child,
                    user=request.user,
                    defaults={
                        "role": invite.role,
                        "created_by": invite.created_by,
                    },
                )
            except IntegrityError:
                # Race condition: another request created the share concurrently
                # Fetch the existing share
                ChildShare.objects.get(child=invite.child, user=request.user)
                created = False

        # Return the child data
        child_serializer = ChildSerializer(invite.child, context={"request": request})
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(child_serializer.data, status=response_status)


# --- Router ---

router = DefaultRouter()
router.register("children", ChildViewSet, basename="child")
router.register("invites", AcceptInviteViewSet, basename="invite")
