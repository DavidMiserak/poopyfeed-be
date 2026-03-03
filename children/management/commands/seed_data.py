import random
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser
from children.models import Child, ChildShare, ShareInvite
from diapers.models import DiaperChange
from feedings.models import Feeding
from naps.models import Nap
from notifications.models import (
    FeedingReminderLog,
    Notification,
    NotificationPreference,
    QuietHours,
)

SEED_DOMAIN = "@seed.poopyfeed.local"
SEED_PASSWORD = "seedpass123"  # noqa: S105  # nosec B105 - intentional seed data


class Command(BaseCommand):
    help = "Seed the database with realistic test data for manual testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing seed data before recreating.",
        )

    def handle(self, *args, **options):
        seed_users = CustomUser.objects.filter(email__endswith=SEED_DOMAIN)

        if seed_users.exists() and not options["flush"]:
            self.stdout.write(
                self.style.WARNING(
                    "Seed data already exists. Use --flush to delete and recreate."
                )
            )
            return

        if seed_users.exists():
            count = seed_users.count()
            seed_users.delete()
            self.stdout.write(f"Flushed {count} seed user(s) and all related data.")

        with transaction.atomic():
            self._seed()

    def _seed(self):
        rng = random.Random(42)  # nosec B311 - deterministic seed data, not crypto
        now = timezone.now()
        today = now.date()

        # === Users ===
        sarah = self._create_user("sarah", "Sarah", "Johnson", "America/New_York")
        michael = self._create_user("michael", "Michael", "Johnson", "America/New_York")
        maria = self._create_user("maria", "Maria", "Garcia", "America/Chicago")
        self.stdout.write("Created 3 users.")

        # === Children (owned by Sarah) ===
        emma = Child.objects.create(
            parent=sarah,
            name="Emma",
            date_of_birth=today - timedelta(days=90),
            gender="F",
            custom_bottle_low_oz=Decimal("2.0"),
            custom_bottle_mid_oz=Decimal("3.0"),
            custom_bottle_high_oz=Decimal("4.0"),
            feeding_reminder_interval=3,
        )
        liam = Child.objects.create(
            parent=sarah,
            name="Liam",
            date_of_birth=today - timedelta(days=540),
            gender="M",
            custom_bottle_low_oz=Decimal("4.0"),
            custom_bottle_mid_oz=Decimal("6.0"),
            custom_bottle_high_oz=Decimal("8.0"),
            feeding_reminder_interval=None,
        )
        noah = Child.objects.create(
            parent=sarah,
            name="Noah",
            date_of_birth=today - timedelta(days=180),
            gender="M",
            custom_bottle_low_oz=Decimal("3.0"),
            custom_bottle_mid_oz=Decimal("4.0"),
            custom_bottle_high_oz=Decimal("5.0"),
            feeding_reminder_interval=4,
        )
        children = [emma, liam, noah]
        self.stdout.write("Created 3 children (Emma, Liam, Noah).")

        # === Sharing ===
        for child in children:
            ChildShare.objects.create(
                child=child, user=michael, role="CO", created_by=sarah
            )
        for child in [emma, noah]:
            ChildShare.objects.create(
                child=child, user=maria, role="CG", created_by=sarah
            )
        ShareInvite.objects.create(
            child=emma,
            token=secrets.token_urlsafe(32),
            role="CG",
            created_by=sarah,
            is_active=True,
        )
        self.stdout.write("Created sharing relationships and 1 invite.")

        # === Tracking events (14 days) ===
        feedings = []
        diapers = []
        naps = []

        for day_offset in range(14, 0, -1):
            day = today - timedelta(days=day_offset)
            feedings += self._generate_feedings(rng, emma, day, "newborn")
            feedings += self._generate_feedings(rng, noah, day, "infant")
            feedings += self._generate_feedings(rng, liam, day, "toddler")
            diapers += self._generate_diapers(rng, emma, day, "newborn")
            diapers += self._generate_diapers(rng, noah, day, "infant")
            diapers += self._generate_diapers(rng, liam, day, "toddler")
            naps += self._generate_naps(rng, emma, day, "newborn")
            naps += self._generate_naps(rng, noah, day, "infant")
            naps += self._generate_naps(rng, liam, day, "toddler")

        Feeding.objects.bulk_create(feedings)
        DiaperChange.objects.bulk_create(diapers)
        Nap.objects.bulk_create(naps)
        self.stdout.write(
            f"Created {len(feedings)} feedings, {len(diapers)} diapers, "
            f"{len(naps)} naps over 14 days."
        )

        # === Notifications ===
        self._create_notification_prefs(sarah, michael, maria, children)
        self._create_sample_notifications(rng, sarah, michael, maria, children, now)
        self.stdout.write("Created notification preferences and sample notifications.")

        # === Summary ===
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(self.style.SUCCESS("Seed data created successfully!"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write("")
        self.stdout.write("Login credentials (password for all: seedpass123):")
        self.stdout.write(f"  Mom:       sarah@seed.poopyfeed.local")
        self.stdout.write(f"  Dad:       michael@seed.poopyfeed.local")
        self.stdout.write(f"  Caretaker: maria@seed.poopyfeed.local")
        self.stdout.write("")
        self.stdout.write(f"Children: Emma (~3mo), Liam (~18mo), Noah (~6mo)")
        self.stdout.write(
            f"Events:   {len(feedings)} feedings, {len(diapers)} "
            f"diapers, {len(naps)} naps"
        )

    def _create_user(self, username_prefix, first_name, last_name, tz):
        email = f"{username_prefix}{SEED_DOMAIN}"
        user = CustomUser.objects.create_user(
            username=email,
            email=email,
            password=SEED_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            timezone=tz,
        )
        return user

    # --- Feeding generation ---

    def _generate_feedings(self, rng, child, day, profile):
        configs = {
            "newborn": {
                "count": (8, 12),
                "breast_pct": 0.6,
                "bottle_oz": (Decimal("2.0"), Decimal("4.0")),
                "breast_min": (5, 25),
                "wake_start": 6,
                "wake_end": 23,
            },
            "infant": {
                "count": (5, 7),
                "breast_pct": 0.3,
                "bottle_oz": (Decimal("3.0"), Decimal("6.0")),
                "breast_min": (8, 20),
                "wake_start": 6,
                "wake_end": 21,
            },
            "toddler": {
                "count": (3, 5),
                "breast_pct": 0.0,
                "bottle_oz": (Decimal("4.0"), Decimal("8.0")),
                "breast_min": (0, 0),
                "wake_start": 7,
                "wake_end": 20,
            },
        }
        cfg = configs[profile]
        count = rng.randint(*cfg["count"])
        results = []

        for slot in self._spread_times(
            rng, day, count, cfg["wake_start"], cfg["wake_end"]
        ):
            if rng.random() < cfg["breast_pct"]:
                results.append(
                    Feeding(
                        child=child,
                        feeding_type="breast",
                        fed_at=slot,
                        amount_oz=None,
                        duration_minutes=rng.randint(*cfg["breast_min"]),
                        side=rng.choice(["left", "right", "both"]),
                    )
                )
            else:
                oz_low, oz_high = cfg["bottle_oz"]
                # Generate in 0.5 oz steps
                steps = int((oz_high - oz_low) / Decimal("0.5"))
                amount = oz_low + Decimal("0.5") * rng.randint(0, steps)
                results.append(
                    Feeding(
                        child=child,
                        feeding_type="bottle",
                        fed_at=slot,
                        amount_oz=amount,
                        duration_minutes=None,
                        side="",
                    )
                )
        return results

    # --- Diaper generation ---

    def _generate_diapers(self, rng, child, day, profile):
        configs = {
            "newborn": {"count": (8, 12)},
            "infant": {"count": (6, 8)},
            "toddler": {"count": (4, 6)},
        }
        cfg = configs[profile]
        count = rng.randint(*cfg["count"])
        results = []

        for slot in self._spread_times(rng, day, count, 6, 22):
            change_type = rng.choices(["wet", "dirty", "both"], weights=[50, 25, 25])[0]
            results.append(
                DiaperChange(
                    child=child,
                    change_type=change_type,
                    changed_at=slot,
                )
            )
        return results

    # --- Nap generation ---

    def _generate_naps(self, rng, child, day, profile):
        configs = {
            "newborn": {"count": (4, 6), "duration": (30, 90)},
            "infant": {"count": (2, 3), "duration": (45, 120)},
            "toddler": {"count": (1, 2), "duration": (60, 150)},
        }
        cfg = configs[profile]
        count = rng.randint(*cfg["count"])
        results = []

        for slot in self._spread_times(rng, day, count, 8, 18):
            duration = rng.randint(*cfg["duration"])
            results.append(
                Nap(
                    child=child,
                    napped_at=slot,
                    ended_at=slot + timedelta(minutes=duration),
                )
            )
        return results

    # --- Time distribution helper ---

    def _spread_times(self, rng, day, count, start_hour, end_hour):
        """Distribute `count` events across a day's wake window with jitter."""
        window_minutes = (end_hour - start_hour) * 60
        interval = window_minutes / max(count, 1)
        times = []
        for i in range(count):
            base_min = int(i * interval)
            jitter = rng.randint(0, max(int(interval * 0.6), 1))
            total_min = start_hour * 60 + base_min + jitter
            hour = total_min // 60
            minute = total_min % 60
            dt = datetime(
                day.year,
                day.month,
                day.day,
                hour,
                minute,
                tzinfo=ZoneInfo("UTC"),
            )
            times.append(dt)
        return times

    # --- Notifications ---

    def _create_notification_prefs(self, sarah, michael, maria, children):
        prefs = []
        for user in [sarah, michael, maria]:
            for child in children:
                # Maria only has access to Emma and Noah
                if user == maria and child.name == "Liam":
                    continue
                prefs.append(
                    NotificationPreference(
                        user=user,
                        child=child,
                        notify_feedings=True,
                        notify_diapers=True,
                        notify_naps=True,
                    )
                )
        NotificationPreference.objects.bulk_create(prefs)

        # Quiet hours
        QuietHours.objects.create(
            user=sarah, enabled=True, start_time=time(22, 0), end_time=time(6, 0)
        )
        QuietHours.objects.create(
            user=michael, enabled=True, start_time=time(23, 0), end_time=time(7, 0)
        )

    def _create_sample_notifications(self, rng, sarah, michael, maria, children, now):
        emma, liam, noah = children
        notifs = []
        templates = [
            (michael, sarah, emma, "feeding", "Sarah logged a feeding for Emma"),
            (michael, sarah, emma, "diaper", "Sarah changed Emma's diaper"),
            (michael, sarah, noah, "nap", "Sarah started a nap for Noah"),
            (sarah, michael, liam, "feeding", "Michael logged a feeding for Liam"),
            (sarah, michael, emma, "diaper", "Michael changed Emma's diaper"),
            (maria, sarah, emma, "feeding", "Sarah logged a feeding for Emma"),
            (maria, sarah, noah, "diaper", "Sarah changed Noah's diaper"),
            (sarah, None, emma, "feeding_reminder", "Emma hasn't been fed in 3 hours"),
            (sarah, None, noah, "feeding_reminder", "Noah hasn't been fed in 4 hours"),
            (michael, sarah, noah, "feeding", "Sarah logged a feeding for Noah"),
            (sarah, maria, emma, "nap", "Maria started a nap for Emma"),
            (michael, maria, emma, "feeding", "Maria logged a feeding for Emma"),
            (sarah, michael, liam, "nap", "Michael started a nap for Liam"),
            (michael, sarah, liam, "diaper", "Sarah changed Liam's diaper"),
        ]

        for i, (recipient, actor, child, event_type, message) in enumerate(templates):
            notifs.append(
                Notification(
                    recipient=recipient,
                    actor=actor,
                    child=child,
                    event_type=event_type,
                    message=message,
                    is_read=(i % 3 == 0),  # ~1/3 read
                )
            )

        Notification.objects.bulk_create(notifs)

        # Manually set created_at to spread over last 2 days
        all_notifs = Notification.objects.filter(
            recipient__email__endswith=SEED_DOMAIN
        ).order_by("id")
        for i, notif in enumerate(all_notifs):
            Notification.objects.filter(pk=notif.pk).update(
                created_at=now - timedelta(hours=i * 3)
            )
