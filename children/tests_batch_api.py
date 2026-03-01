"""Tests for batch event creation API (catch-up mode)."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from diapers.models import DiaperChange
from django_project.test_constants import TEST_PASSWORD
from feedings.models import Feeding
from naps.models import Nap

from .models import Child, ChildShare

User = get_user_model()

# Test timestamp constants
TEST_DATE = "2024-02-17"
TEST_TIME_1000 = f"{TEST_DATE}T10:00:00Z"
TEST_TIME_1025 = f"{TEST_DATE}T10:25:00Z"
TEST_TIME_1030 = f"{TEST_DATE}T10:30:00Z"
TEST_TIME_1100 = f"{TEST_DATE}T11:00:00Z"
TEST_TIME_1130 = f"{TEST_DATE}T11:30:00Z"

# Test event payloads
FEEDING_BOTTLE_EVENT = {
    "type": "feeding",
    "data": {
        "feeding_type": "bottle",
        "fed_at": TEST_TIME_1000,
        "amount_oz": 4.0,
    },
}

FEEDING_BOTTLE_EVENT_1025 = {
    "type": "feeding",
    "data": {
        "feeding_type": "bottle",
        "fed_at": TEST_TIME_1025,
        "amount_oz": 4.0,
    },
}

FEEDING_BREAST_EVENT = {
    "type": "feeding",
    "data": {
        "feeding_type": "breast",
        "fed_at": TEST_TIME_1000,
    },
}

DIAPER_WET_EVENT = {
    "type": "diaper",
    "data": {
        "change_type": "wet",
        "changed_at": TEST_TIME_1000,
    },
}

DIAPER_WET_EVENT_1025 = {
    "type": "diaper",
    "data": {
        "change_type": "wet",
        "changed_at": TEST_TIME_1025,
    },
}

NAP_EVENT = {
    "type": "nap",
    "data": {
        "napped_at": TEST_TIME_1000,
        "ended_at": TEST_TIME_1100,
    },
}

NAP_EVENT_1030 = {
    "type": "nap",
    "data": {
        "napped_at": TEST_TIME_1030,
        "ended_at": TEST_TIME_1130,
    },
}


class BatchCreateAPITest(TestCase):
    """Test batch event creation endpoint."""

    @classmethod
    def setUpTestData(cls):
        """Set up test users and child."""
        # Create users
        cls.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password=TEST_PASSWORD
        )
        cls.co_parent = User.objects.create_user(
            username="coparent", email="coparent@example.com", password=TEST_PASSWORD
        )
        cls.caregiver = User.objects.create_user(
            username="caregiver", email="caregiver@example.com", password=TEST_PASSWORD
        )
        cls.other_user = User.objects.create_user(
            username="other", email="other@example.com", password=TEST_PASSWORD
        )

        # Create child owned by owner
        cls.child = Child.objects.create(
            parent=cls.owner, name="Baby Alice", date_of_birth="2024-01-15"
        )

        # Add co-parent and caregiver
        ChildShare.objects.create(
            child=cls.child, user=cls.co_parent, role=ChildShare.Role.CO_PARENT
        )
        ChildShare.objects.create(
            child=cls.child, user=cls.caregiver, role=ChildShare.Role.CAREGIVER
        )

    def setUp(self):
        """Set up API client for each test."""
        self.client = APIClient()
        self.url = f"/api/v1/children/{self.child.id}/batch/"

    # --- Permission Tests ---

    def test_batch_requires_authentication(self):
        """Test that batch endpoint requires authentication."""
        response = self.client.post(self.url, {"events": []})
        self.assertEqual(response.status_code, 401)

    def test_batch_owner_can_create(self):
        """Test that owner can create batch events."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {"events": [FEEDING_BOTTLE_EVENT]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["count"], 1)

    def test_batch_co_parent_can_create(self):
        """Test that co-parent can create batch events."""
        self.client.force_authenticate(self.co_parent)
        response = self.client.post(
            self.url,
            {"events": [FEEDING_BOTTLE_EVENT]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_batch_caregiver_can_create(self):
        """Test that caregiver can create batch events."""
        self.client.force_authenticate(self.caregiver)
        response = self.client.post(
            self.url,
            {"events": [FEEDING_BOTTLE_EVENT]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_batch_unauthorized_user_denied(self):
        """Test that unauthorized user cannot create batch events."""
        self.client.force_authenticate(self.other_user)
        response = self.client.post(
            self.url,
            {"events": [FEEDING_BOTTLE_EVENT]},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_batch_nonexistent_child_returns_404(self):
        """Test batch endpoint returns 404 for nonexistent child."""
        self.client.force_authenticate(self.owner)
        url = f"/api/v1/children/9999/batch/"
        response = self.client.post(url, {"events": []}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_batch_invalid_event_type_rejected(self):
        """Invalid event type returns 400 and mentions allowed types."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {
                "events": [
                    {
                        "type": "sleep",
                        "data": {"napped_at": TEST_TIME_1000},
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("events", response.data)

    def test_batch_more_than_20_events_rejected(self):
        """More than 20 events in one batch returns 400."""
        self.client.force_authenticate(self.owner)
        events = [FEEDING_BOTTLE_EVENT] * 21
        response = self.client.post(
            self.url,
            {"events": events},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("events", response.data)

    def test_batch_save_exception_returns_generic_error(self):
        """When save raises, view returns 400 with generic message (no internal leak)."""
        self.client.force_authenticate(self.owner)
        with patch(
            "feedings.api.NestedFeedingSerializer.save",
            side_effect=Exception("DB error"),
        ):
            response = self.client.post(
                self.url,
                {"events": [FEEDING_BOTTLE_EVENT]},
                format="json",
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)
        self.assertIn("Failed to save events", response.data["detail"])
        self.assertEqual(Feeding.objects.filter(child=self.child).count(), 0)

    def test_get_event_serializer_unknown_type_raises(self):
        """_get_event_serializer raises ValueError for unknown event type."""
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .batch_api import BatchCreateView

        factory = APIRequestFactory()
        request = factory.post("/")
        force_authenticate(request, user=self.owner)
        view = BatchCreateView()
        view.request = request
        view.format_kwarg = None
        with self.assertRaises(ValueError) as ctx:
            view._get_event_serializer("unknown", {}, self.child)
        self.assertIn("Unknown event type", str(ctx.exception))

    def test_get_model_for_type_unknown_raises(self):
        """_get_model_for_type raises ValueError for unknown event type."""
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .batch_api import BatchCreateView

        factory = APIRequestFactory()
        request = factory.post("/")
        force_authenticate(request, user=self.owner)
        view = BatchCreateView()
        view.request = request
        with self.assertRaises(ValueError) as ctx:
            view._get_model_for_type("other")
        self.assertIn("Unknown event type", str(ctx.exception))

    def test_batch_event_serializer_validate_type_invalid_raises(self):
        """BatchEventSerializer.validate_type raises for invalid type."""
        from rest_framework.exceptions import ValidationError

        from .batch_api import BatchEventSerializer

        serializer = BatchEventSerializer()
        with self.assertRaises(ValidationError) as ctx:
            serializer.validate_type("invalid")
        self.assertIn("Invalid event type", str(ctx.exception))

    def test_batch_create_serializer_validate_events_valid_returns(self):
        """BatchCreateSerializer.validate_events returns value when 1–20 events."""
        from .batch_api import BatchCreateSerializer

        serializer = BatchCreateSerializer()
        value = [
            {
                "type": "feeding",
                "data": {
                    "feeding_type": "bottle",
                    "fed_at": TEST_TIME_1000,
                    "amount_oz": 4.0,
                },
            }
        ]
        result = serializer.validate_events(value)
        self.assertEqual(result, value)

    def test_batch_create_serializer_validate_events_more_than_20_raises(self):
        """BatchCreateSerializer.validate_events raises when given more than 20 events."""
        from rest_framework.exceptions import ValidationError

        from .batch_api import BatchCreateSerializer

        serializer = BatchCreateSerializer()
        value = [FEEDING_BOTTLE_EVENT] * 21
        with self.assertRaises(ValidationError) as ctx:
            serializer.validate_events(value)
        self.assertIn("Maximum 20 events per batch", str(ctx.exception))

    # --- Successful Creation Tests ---

    def test_batch_create_single_feeding(self):
        """Test creating a single feeding via batch."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {"events": [FEEDING_BOTTLE_EVENT]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["created"]), 1)
        self.assertEqual(response.data["created"][0]["type"], "feeding")
        self.assertIn("id", response.data["created"][0])

        # Verify feeding was created in database
        self.assertEqual(Feeding.objects.filter(child=self.child).count(), 1)
        feeding = Feeding.objects.get(child=self.child)
        self.assertEqual(feeding.feeding_type, "bottle")
        self.assertEqual(feeding.amount_oz, 4.0)

    def test_batch_create_single_diaper(self):
        """Test creating a single diaper change via batch."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {"events": [DIAPER_WET_EVENT]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["created"][0]["type"], "diaper")

        # Verify diaper was created
        self.assertEqual(DiaperChange.objects.filter(child=self.child).count(), 1)
        diaper = DiaperChange.objects.get(child=self.child)
        self.assertEqual(diaper.change_type, "wet")

    def test_batch_create_single_nap(self):
        """Test creating a single nap via batch."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {"events": [NAP_EVENT]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["created"][0]["type"], "nap")

        # Verify nap was created
        self.assertEqual(Nap.objects.filter(child=self.child).count(), 1)

    def test_batch_create_mixed_events(self):
        """Test creating mixed event types in a single batch."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {
                "events": [
                    FEEDING_BOTTLE_EVENT,
                    DIAPER_WET_EVENT_1025,
                    NAP_EVENT_1030,
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["created"]), 3)

        # Verify all events were created
        self.assertEqual(Feeding.objects.filter(child=self.child).count(), 1)
        self.assertEqual(DiaperChange.objects.filter(child=self.child).count(), 1)
        self.assertEqual(Nap.objects.filter(child=self.child).count(), 1)

    def test_batch_create_20_events(self):
        """Test creating maximum 20 events in a batch."""
        self.client.force_authenticate(self.owner)

        events = [
            {
                "type": "feeding",
                "data": {
                    "feeding_type": "bottle",
                    "fed_at": f"2024-02-17T{10 + (i % 14):02d}:{(i * 5) % 60:02d}:00Z",
                    "amount_oz": 4.0,
                },
            }
            for i in range(20)
        ]

        response = self.client.post(self.url, {"events": events}, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["count"], 20)
        self.assertEqual(Feeding.objects.filter(child=self.child).count(), 20)

    # --- Validation Error Tests ---

    def test_batch_missing_events_field(self):
        """Test batch request without events field."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("events", response.data)

    def test_batch_empty_events_list(self):
        """Test batch with empty events list."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.url, {"events": []}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_batch_exceeds_20_events(self):
        """Test batch with more than 20 events is rejected."""
        self.client.force_authenticate(self.owner)

        events = [
            {
                "type": "feeding",
                "data": {
                    "feeding_type": "bottle",
                    "fed_at": f"2024-02-17T{10 + i:02d}:00:00Z",
                    "amount_oz": 4.0,
                },
            }
            for i in range(21)
        ]

        response = self.client.post(self.url, {"events": events}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("events", response.data)

    def test_batch_invalid_event_type(self):
        """Test batch with invalid event type."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {"events": [{"type": "invalid", "data": {}}]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("events", response.data)

    def test_batch_feeding_missing_amount_oz(self):
        """Test feeding validation: missing amount_oz for bottle feeding."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {
                "events": [
                    {
                        "type": "feeding",
                        "data": {
                            "feeding_type": "bottle",
                            "fed_at": TEST_TIME_1000,
                        },
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.data)
        self.assertEqual(len(response.data["errors"]), 1)
        self.assertEqual(response.data["errors"][0]["index"], 0)
        self.assertEqual(response.data["errors"][0]["type"], "feeding")
        self.assertIn("amount_oz", response.data["errors"][0]["errors"])

    def test_batch_feeding_missing_duration_for_breast(self):
        """Test feeding validation: missing duration for breast feeding."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {"events": [FEEDING_BREAST_EVENT]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.data)

    def test_batch_multiple_validation_errors(self):
        """Test batch with multiple events having validation errors."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {
                "events": [
                    {
                        "type": "feeding",
                        "data": {
                            "feeding_type": "bottle",
                            "fed_at": TEST_TIME_1000,
                        },
                    },
                    {
                        "type": "nap",
                        "data": {
                            "napped_at": "2024-02-17T10:30:00Z",
                            "ended_at": TEST_TIME_1000,
                        },
                    },
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.data)
        self.assertEqual(len(response.data["errors"]), 2)

    def test_batch_error_prevents_any_creation(self):
        """Test that if any event fails validation, no events are created (atomicity)."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {
                "events": [
                    FEEDING_BOTTLE_EVENT,
                    {
                        "type": "feeding",
                        "data": {
                            "feeding_type": "bottle",
                            "fed_at": "2024-02-17T10:25:00Z",
                        },
                    },
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        # Verify no feedings were created (atomic rollback)
        self.assertEqual(Feeding.objects.filter(child=self.child).count(), 0)

    # --- Diaper Change Validation Tests ---

    def test_batch_diaper_missing_change_type(self):
        """Test diaper validation: missing change_type."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {
                "events": [
                    {
                        "type": "diaper",
                        "data": {
                            "changed_at": TEST_TIME_1000,
                        },
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.data)

    def test_batch_diaper_invalid_change_type(self):
        """Test diaper validation: invalid change_type."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {
                "events": [
                    {
                        "type": "diaper",
                        "data": {
                            "change_type": "invalid",
                            "changed_at": TEST_TIME_1000,
                        },
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.data)

    # --- Nap Validation Tests ---

    def test_batch_nap_ended_at_before_napped_at(self):
        """Test nap validation: ended_at before napped_at."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {
                "events": [
                    {
                        "type": "nap",
                        "data": {
                            "napped_at": TEST_TIME_1100,
                            "ended_at": TEST_TIME_1000,
                        },
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.data)

    def test_batch_nap_missing_napped_at(self):
        """Test nap validation: missing napped_at."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {
                "events": [
                    {
                        "type": "nap",
                        "data": {
                            "ended_at": TEST_TIME_1100,
                        },
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.data)

    # --- Response Format Tests ---

    def test_batch_response_includes_all_fields(self):
        """Test that batch response includes full serialized objects."""
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.url,
            {"events": [FEEDING_BOTTLE_EVENT]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        created = response.data["created"][0]

        # Verify required fields in response
        self.assertIn("type", created)
        self.assertIn("id", created)
        self.assertIn("feeding_type", created)
        self.assertIn("fed_at", created)
        self.assertIn("amount_oz", created)
        self.assertIn("created_at", created)
        self.assertIn("updated_at", created)
