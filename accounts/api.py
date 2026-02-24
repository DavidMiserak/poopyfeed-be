from zoneinfo import available_timezones

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()


@csrf_protect
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_auth_token(request):
    """Get or create auth token for the current user.

    Security: Uses POST to prevent CSRF and token leakage via browser cache/referrers.
    CSRF protection explicitly enabled (not via middleware exemption).
    """
    token, created = Token.objects.get_or_create(user=request.user)
    return Response({"auth_token": token.key}, status=status.HTTP_200_OK)


# --- Account Serializers ---


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "timezone"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        user = self.context["request"].user
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_timezone(self, value):
        if value not in available_timezones():
            raise serializers.ValidationError("Invalid timezone.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "New passwords do not match."}  # nosec B105
            )
        try:
            validate_password(attrs["new_password"], self.context["request"].user)
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        return attrs


class DeleteAccountSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value


# --- Account Views ---


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()

        # Rotate token: delete old, create new
        Token.objects.filter(user=user).delete()
        new_token = Token.objects.create(user=user)

        return Response(
            {"detail": "Password changed successfully.", "auth_token": new_token.key}
        )


class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeleteAccountSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
