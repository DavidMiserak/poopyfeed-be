"""REST API for children app: Child, ChildShare, ShareInvite."""

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from .api_permissions import CanEditChild, CanManageSharing, HasChildAccess
from .models import Child, ChildShare, ShareInvite

# --- Serializers ---


class ChildSerializer(serializers.ModelSerializer):
    """Child serializer with computed permission fields."""

    user_role = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_manage_sharing = serializers.SerializerMethodField()

    class Meta:
        model = Child
        fields = [
            "id",
            "name",
            "date_of_birth",
            "gender",
            "created_at",
            "updated_at",
            "user_role",
            "can_edit",
            "can_manage_sharing",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_user_role(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.get_user_role(request.user)
        return None

    def get_can_edit(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.can_edit(request.user)
        return False

    def get_can_manage_sharing(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.can_manage_sharing(request.user)
        return False


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
    """ViewSet for Child CRUD operations."""

    serializer_class = ChildSerializer
    permission_classes = [IsAuthenticated, HasChildAccess]

    def get_queryset(self):
        """Return children accessible to the current user."""
        return Child.for_user(self.request.user)

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
            invites = child.invites.all()
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
    """ViewSet for accepting invites."""

    permission_classes = [IsAuthenticated]

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
