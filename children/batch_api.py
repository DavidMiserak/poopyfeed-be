"""Batch creation API for catch-up mode.

Allows atomic creation of multiple mixed tracking events (feedings, diapers, naps)
in a single request. All events are validated and created within a database transaction.
"""

from django.db import transaction
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django_project.throttles import TrackingCreateThrottle

from diapers.api import NestedDiaperChangeSerializer
from diapers.models import DiaperChange
from feedings.api import NestedFeedingSerializer
from feedings.models import Feeding
from naps.api import NestedNapSerializer
from naps.models import Nap

from .api_permissions import HasChildAccess
from .models import Child


class BatchEventSerializer(serializers.Serializer):
    """Serializer for a single event within a batch request."""

    type = serializers.ChoiceField(choices=["feeding", "diaper", "nap"])
    data = serializers.DictField()

    def validate_type(self, value):
        """Validate event type is supported."""
        valid_types = ["feeding", "diaper", "nap"]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid event type. Must be one of: {', '.join(valid_types)}"
            )
        return value


class BatchCreateSerializer(serializers.Serializer):
    """Main serializer for batch creation request.

    Validates the overall batch structure and delegates per-event validation
    to type-specific serializers (FeedingSerializer, DiaperChangeSerializer, NapSerializer).
    """

    events = serializers.ListField(
        child=BatchEventSerializer(),
        required=True,
        min_length=1,
        max_length=20,
    )

    def validate_events(self, value):
        """Validate events list and individual event data."""
        if not value:
            raise serializers.ValidationError("At least one event is required.")
        if len(value) > 20:
            raise serializers.ValidationError("Maximum 20 events per batch.")
        return value

    def validate(self, data):
        """Perform cross-event validation if needed."""
        return data


class BatchCreateView(APIView):
    """API view for batch creation of mixed tracking events.

    Endpoint: POST /api/v1/children/<child_pk>/batch/
    Request body:
    {
        "events": [
            {
                "type": "feeding",
                "data": {
                    "feeding_type": "bottle",
                    "fed_at": "2026-02-17T10:00:00Z",
                    "amount_oz": 4.0
                }
            },
            ...
        ]
    }

    Response (201 Created):
    {
        "created": [
            {"type": "feeding", "id": 42, ...full serialized object...},
            ...
        ],
        "count": 3
    }

    Response (400 Bad Request) on validation errors:
    {
        "errors": [
            {
                "index": 0,
                "type": "feeding",
                "errors": {
                    "amount_oz": ["This field is required for bottle feedings."]
                }
            }
        ]
    }
    """

    permission_classes = [IsAuthenticated, HasChildAccess]
    throttle_classes = [TrackingCreateThrottle]

    def get_child(self):
        """Get and validate child access."""
        child_pk = self.kwargs.get("child_pk")
        try:
            child = Child.objects.get(pk=child_pk)
        except Child.DoesNotExist:
            return None

        if not child.has_access(self.request.user):
            raise PermissionDenied("You do not have access to this child.")

        return child

    def post(self, request, *args, **kwargs):
        """Handle batch event creation."""
        # Get and validate child access
        child = self.get_child()
        if not child:
            return Response(
                {"detail": "Child not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate batch request structure
        batch_serializer = BatchCreateSerializer(data=request.data)
        if not batch_serializer.is_valid():
            return Response(batch_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        events = batch_serializer.validated_data.get("events", [])

        # Validate individual events and collect per-event errors
        event_errors = []
        validated_events = []

        for index, event in enumerate(events):
            event_type = event.get("type")
            event_data = event.get("data", {})

            # Get appropriate serializer for this event type
            serializer = self._get_event_serializer(
                event_type, event_data, child
            )

            if serializer.is_valid():
                validated_events.append(
                    {
                        "type": event_type,
                        "serializer": serializer,
                        "model": self._get_model_for_type(event_type),
                    }
                )
            else:
                event_errors.append(
                    {
                        "index": index,
                        "type": event_type,
                        "errors": serializer.errors,
                    }
                )

        # If any events failed validation, return all errors without saving
        if event_errors:
            return Response(
                {"errors": event_errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # All events are valid - create them atomically
        try:
            with transaction.atomic():
                created_objects = []
                for event_info in validated_events:
                    serializer = event_info["serializer"]
                    obj = serializer.save(child=child)
                    created_objects.append(
                        {
                            "type": event_info["type"],
                            "object": obj,
                            "serializer": serializer,
                        }
                    )

            # Serialize created objects for response
            response_data = {
                "created": [
                    {
                        "type": item["type"],
                        "id": item["object"].id,
                        **item["serializer"].to_representation(item["object"]),
                    }
                    for item in created_objects
                ],
                "count": len(created_objects),
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            # Transaction rolled back automatically
            # Return generic error to avoid leaking internal details
            return Response(
                {
                    "detail": "Failed to save events. Please check your data and try again."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _get_event_serializer(self, event_type, event_data, child):
        """Get the appropriate serializer for the event type."""
        if event_type == "feeding":
            return NestedFeedingSerializer(data=event_data, context={"request": self.request})
        elif event_type == "diaper":
            return NestedDiaperChangeSerializer(
                data=event_data, context={"request": self.request}
            )
        elif event_type == "nap":
            return NestedNapSerializer(data=event_data, context={"request": self.request})
        else:
            raise ValueError(f"Unknown event type: {event_type}")

    def _get_model_for_type(self, event_type):
        """Get the model class for the event type."""
        if event_type == "feeding":
            return Feeding
        elif event_type == "diaper":
            return DiaperChange
        elif event_type == "nap":
            return Nap
        else:
            raise ValueError(f"Unknown event type: {event_type}")
