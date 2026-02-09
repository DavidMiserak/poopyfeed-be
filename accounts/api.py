from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_auth_token(request):
    """Get or create auth token for the current user."""
    token, created = Token.objects.get_or_create(user=request.user)
    return Response({"auth_token": token.key}, status=status.HTTP_200_OK)
