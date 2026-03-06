from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Literal

from django.utils import timezone

AutoCheckStatus = Literal["ok", "warning", "missing", "none"]

FussBusSymptomId = Literal[
    "crying",
    "refusing_food",
    "wont_sleep",
    "general_fussiness",
]


@dataclass
class AgeRange:
    min_months: float | None = None
    max_months: float | None = None


def is_in_age_range(months: float, age_range: AgeRange) -> bool:
    if age_range.min_months is not None and months < age_range.min_months:
        return False
    if age_range.max_months is not None and months > age_range.max_months:
        return False
    return True


@dataclass
class AutoCheckState:
    fed: AutoCheckStatus
    fed_detail: str | None
    diaper: AutoCheckStatus
    diaper_detail: str | None
    nap: AutoCheckStatus
    nap_detail: str | None


@dataclass
class ChecklistItemDef:
    id: str
    label: str
    symptom_ids: tuple[FussBusSymptomId, ...]
    age_range: AgeRange | None = None
    # Action-oriented text for step 3 when this item was not marked (label is for step 2 "already considered").
    suggestion_text: str | None = None


@dataclass
class ChecklistItem:
    id: str
    label: str
    kind: Literal["auto", "manual"]
    auto_status: AutoCheckStatus | None = None
    detail: str | None = None
    interactive: bool = False


@dataclass
class PrioritizedSuggestion:
    text: str
    priority: Literal["high", "medium", "low"]


@dataclass
class SymptomType:
    id: FussBusSymptomId
    label: str
    description: str
    min_age_months: float | None = None


@dataclass
class SoothingCategory:
    title: str
    items: list[str]


@dataclass
class DevelopmentalContext:
    age_range: AgeRange
    text: str


@dataclass
class GlossarySong:
    title: str
    lyrics: str


@dataclass
class GlossaryEntry:
    title: str
    body: str
    songs: list[GlossarySong] | None = None


FUSS_BUS_SYMPTOM_IDS: tuple[FussBusSymptomId, ...] = (
    "crying",
    "refusing_food",
    "wont_sleep",
    "general_fussiness",
)

SYMPTOM_TYPES: list[SymptomType] = [
    SymptomType(
        id="crying",
        label="Crying",
        description="General distress, inconsolable",
    ),
    SymptomType(
        id="refusing_food",
        label="Refusing food",
        description="Fussy eating, not interested",
        min_age_months=12,
    ),
    SymptomType(
        id="wont_sleep",
        label="Won't sleep",
        description="Fighting naps, restless",
    ),
    SymptomType(
        id="general_fussiness",
        label="General fussiness",
        description="Irritable, clingy, unsettled",
    ),
]

# Manual checklist definitions (ported from front-end fuss-bus.data.ts)
# Labels are phrased supportively so caregivers don't feel judged.
COMMON_MANUAL_ITEMS: list[ChecklistItemDef] = [
    ChecklistItemDef(
        id="comfortable_temperature",
        label="Temperature seems comfortable (not too hot or cold)",
        symptom_ids=(),
        suggestion_text="Check that the room or baby isn't too hot or cold.",
    ),
    ChecklistItemDef(
        id="not_overstimulated",
        label="Environment is calm (not overstimulating)",
        symptom_ids=(),
        suggestion_text="Try a calmer environment — dim lights, less noise.",
    ),
    ChecklistItemDef(
        id="held_comforted",
        label="They've been held or comforted recently",
        symptom_ids=(),
        suggestion_text="Offer a cuddle or hold — sometimes contact is what they need.",
    ),
]

AGE_FILTERED_ITEMS: list[ChecklistItemDef] = [
    ChecklistItemDef(
        id="no_teething",
        label="No signs of teething right now",
        symptom_ids=(),
        age_range=AgeRange(min_months=4, max_months=24),
        suggestion_text="If teething might be involved, a chilled teething ring can help.",
    ),
    ChecklistItemDef(
        id="no_illness",
        label="No signs of illness (e.g. fever, rash, vomiting)",
        symptom_ids=(),
        suggestion_text="If you notice fever, rash, or vomiting, contact your pediatrician.",
    ),
    ChecklistItemDef(
        id="not_growth_spurt",
        label="Doesn't seem to be a growth spurt (common around 2–3 weeks, 6 weeks, 3 months)",
        symptom_ids=(),
        suggestion_text="Growth spurts can increase hunger and fussiness — try offering more frequent feeds.",
    ),
    ChecklistItemDef(
        id="no_separation_anxiety",
        label="Separation anxiety doesn't seem to be the cause",
        symptom_ids=(),
        age_range=AgeRange(min_months=6),
        suggestion_text="If separation anxiety fits, extra reassurance and consistent routines can help.",
    ),
]

SYMPTOM_SPECIFIC_ITEMS: list[ChecklistItemDef] = [
    ChecklistItemDef(
        id="gas_burping",
        label="Burping or gas relief already tried",
        symptom_ids=("crying",),
        suggestion_text="Try burping or a gentle gas-relief hold (e.g. colic hold).",
    ),
    ChecklistItemDef(
        id="witching_hour",
        label="It's the witching hour (late afternoon fussiness, 0–4 months)",
        symptom_ids=("crying",),
        age_range=AgeRange(max_months=4),
        suggestion_text="Late-afternoon fussiness is common at this age — soothing and taking shifts can help.",
    ),
    ChecklistItemDef(
        id="offering_variety",
        label="Offering variety without pressure",
        symptom_ids=("refusing_food",),
        suggestion_text="Offer a variety of foods without pressure — appetite varies day to day.",
    ),
    ChecklistItemDef(
        id="mealtime_relaxed",
        label="Mealtimes feel relaxed",
        symptom_ids=("refusing_food",),
        suggestion_text="Keep mealtimes low-pressure and relaxed when you can.",
    ),
    ChecklistItemDef(
        id="milk_intake",
        label="Milk under 400ml/day if 12+ months (optional to consider)",
        symptom_ids=("refusing_food",),
        age_range=AgeRange(min_months=12),
        suggestion_text="If 12+ months, milk under 400ml/day leaves room for solid foods.",
    ),
    ChecklistItemDef(
        id="sleep_routine",
        label="Sleep routine is consistent",
        symptom_ids=("wont_sleep",),
        suggestion_text="A consistent bedtime and wind-down routine can help.",
    ),
    ChecklistItemDef(
        id="dark_quiet_room",
        label="Sleep space is dark and quiet",
        symptom_ids=("wont_sleep",),
        suggestion_text="Try a dark, quiet sleep space to support settling.",
    ),
    ChecklistItemDef(
        id="not_overtired",
        label="Doesn't seem overtired (sleep window not missed)",
        symptom_ids=("wont_sleep",),
        suggestion_text="If they're overtired, try offering sleep a bit earlier next time.",
    ),
]

MANUAL_CHECKLIST_DEFS: list[ChecklistItemDef] = [
    *COMMON_MANUAL_ITEMS,
    *AGE_FILTERED_ITEMS,
    *SYMPTOM_SPECIFIC_ITEMS,
]

SOOTHING_TOOLKIT: list[SoothingCategory] = [
    SoothingCategory(
        title="Comforting Touch",
        items=["Rock", "Cuddle", "Massage", "Baby carrier", "Colic hold"],
    ),
    SoothingCategory(
        title="Calming Sounds",
        items=["White noise", "Soft music", "Singing"],
    ),
    SoothingCategory(
        title="Rhythmic Motion",
        items=["Stroller walk", "Car ride", "Gentle bouncing"],
    ),
    SoothingCategory(
        title="Other",
        items=["Warm bath", "Swaddling", "Pacifier"],
    ),
]

WHEN_TO_CALL_DOCTOR_BULLETS: list[str] = [
    "Fever (temperature thresholds by age)",
    "Persistent vomiting or diarrhea",
    "Rash or unusual skin changes",
    "Crying that sounds different from normal",
    "Lethargy or unresponsiveness",
    "Refusing fluids for extended period",
]

SELF_CARE_ITEMS: list[str] = [
    "Never shake a baby. Shaking can cause severe brain damage or death. If you feel overwhelmed, put the baby in a safe place and step away.",
    "Take a break: put the baby in a safe place (e.g. crib) and go to another room for 10–15 minutes. Take deep breaths, listen to music, or call a friend.",
    "Ask for and accept help — let your partner, family, or friends help with baby care, chores, or errands so you can rest.",
    "Trust your instincts — you know your child best. If crying seems different or you see signs of illness, contact your pediatrician.",
]

COLIC_SECTION: dict[str, str] = {
    "title": "About colic",
    "body": (
        "Colic is often described by the 3-3-3 rule: crying more than 3 hours per day, "
        "more than 3 days per week, for 3 or more weeks. It often peaks around 6 weeks "
        "and usually resolves by 3–4 months. Talk to your pediatrician for support and "
        "to rule out other causes; use soothing techniques and prioritize your own self-care."
    ),
}

DEVELOPMENTAL_CONTEXTS: list[DevelopmentalContext] = [
    DevelopmentalContext(
        age_range=AgeRange(max_months=4),
        text="Witching hour (late afternoon fussiness) is normal and temporary.",
    ),
    DevelopmentalContext(
        age_range=AgeRange(min_months=0, max_months=1),
        text=(
            "Growth spurts cause increased hunger and fussiness — increase feeding frequency."
        ),
    ),
    DevelopmentalContext(
        age_range=AgeRange(min_months=1.5, max_months=2),
        text=(
            "Growth spurts cause increased hunger and fussiness — increase feeding frequency."
        ),
    ),
    DevelopmentalContext(
        age_range=AgeRange(min_months=2.5, max_months=4),
        text=(
            "Growth spurts cause increased hunger and fussiness — increase feeding frequency."
        ),
    ),
    DevelopmentalContext(
        age_range=AgeRange(min_months=4, max_months=24),
        text="Teething can cause discomfort — offer a chilled teething ring.",
    ),
    DevelopmentalContext(
        age_range=AgeRange(min_months=6),
        text="Separation anxiety is normal — offer reassurance and consistent routines.",
    ),
    DevelopmentalContext(
        age_range=AgeRange(min_months=12),
        text="Appetite naturally decreases after the first year — don't force feed.",
    ),
]

FUSS_BUS_GLOSSARY: dict[str, GlossaryEntry] = {
    "Colic hold": GlossaryEntry(
        title="Colic hold",
        body=(
            "Hold your baby tummy-down along your forearm, with their head near your elbow. "
            "The gentle pressure and position can help relieve gas and soothe fussiness."
        ),
    ),
    "Swaddling": GlossaryEntry(
        title="Swaddling",
        body=(
            "Wrap your baby snugly in a thin blanket with arms at their sides. "
            "It can mimic the womb and help calm. Stop once baby can roll."
        ),
    ),
    "White noise": GlossaryEntry(
        title="White noise",
        body=(
            "Steady, soothing sound like a fan, vacuum, or dedicated machine. "
            "It can help babies settle by masking sudden noises and reminding "
            "them of sounds in the womb."
        ),
    ),
    "Baby carrier": GlossaryEntry(
        title="Baby carrier",
        body=(
            "A sling or carrier lets you hold your baby close hands-free. "
            "The contact and motion often soothe fussiness and can help with bonding."
        ),
    ),
    "Witching hour": GlossaryEntry(
        title="Witching hour",
        body=(
            "A regular fussy period in the late afternoon or evening in the first few months, "
            "often linked to development and overstimulation. It's normal and temporary; "
            "soothing techniques and taking shifts with a partner can help."
        ),
    ),
    "Teething": GlossaryEntry(
        title="Teething",
        body=(
            "Sore, swollen gums can cause discomfort. Offer a chilled (not frozen) teething ring "
            "or gently massage the gums. Ask your doctor about pain relief if needed."
        ),
    ),
    "Growth spurts": GlossaryEntry(
        title="Growth spurts",
        body=(
            "Babies often have growth spurts around 2–3 weeks, 6 weeks, and 3 months, "
            "with increased hunger and fussiness. Increase feeding frequency; behavior "
            "usually normalizes as supply and demand adjust."
        ),
    ),
    "Colic": GlossaryEntry(
        title="Colic",
        body=(
            "Intense, inconsolable crying for more than 3 hours per day, more than 3 days per week, "
            "for 3 or more weeks. It often peaks around 6 weeks and usually resolves by 3–4 months. "
            "Talk to your pediatrician to rule out other causes and to get support; parent self-care "
            "is important."
        ),
    ),
    "Separation anxiety": GlossaryEntry(
        title="Separation anxiety",
        body=(
            "Around 6–8 months, babies may cry when a caregiver leaves. This is normal. "
            "Offer reassurance, practice short separations, and keep routines consistent."
        ),
    ),
    "Rock": GlossaryEntry(
        title="Rocking",
        body=(
            "Gentle rocking in your arms or a chair can calm a fussy baby by providing motion and closeness."
        ),
    ),
    "Cuddle": GlossaryEntry(
        title="Cuddling",
        body=(
            "Holding your baby close helps them feel secure. You cannot spoil a baby by responding "
            "to their need for comfort."
        ),
    ),
    "Massage": GlossaryEntry(
        title="Baby massage",
        body=(
            "Gentle tummy massage or 'bicycle legs' (moving baby's legs in a pedaling motion) "
            "can help relieve gas. Use a light touch and a calm environment."
        ),
    ),
    "Pacifier": GlossaryEntry(
        title="Pacifier",
        body=(
            "Non-nutritive sucking can help babies self-soothe. Use a pacifier if your baby finds it comforting; "
            "follow safe sleep guidelines."
        ),
    ),
}

FUSS_BUS_GLOSSARY["Singing"] = GlossaryEntry(
    title="Singing",
    body=(
        "Your voice is one of the most soothing sounds for your baby. "
        "Try these classic public-domain lullabies — simple, repetitive tunes many babies find calming."
    ),
    songs=[
        GlossarySong(
            title="Twinkle, Twinkle, Little Star",
            lyrics=(
                "Twinkle, twinkle, little star,\n"
                "How I wonder what you are!\n"
                "Up above the world so high,\n"
                "Like a diamond in the sky.\n"
                "Twinkle, twinkle, little star,\n"
                "How I wonder what you are!"
            ),
        ),
        GlossarySong(
            title="Rock-a-bye Baby",
            lyrics=(
                "Rock-a-bye baby, on the treetop,\n"
                "When the wind blows, the cradle will rock,\n"
                "When the bough breaks, the cradle will fall,\n"
                "And down will come baby, cradle and all."
            ),
        ),
        GlossarySong(
            title="Mary Had a Little Lamb",
            lyrics=(
                "Mary had a little lamb,\n"
                "Little lamb, little lamb,\n"
                "Mary had a little lamb,\n"
                "Its fleece was white as snow.\n\n"
                "And everywhere that Mary went,\n"
                "Mary went, Mary went,\n"
                "Everywhere that Mary went,\n"
                "The lamb was sure to go."
            ),
        ),
        GlossarySong(
            title="Row, Row, Row Your Boat",
            lyrics=(
                "Row, row, row your boat\n"
                "Gently down the stream.\n"
                "Merrily, merrily, merrily, merrily,\n"
                "Life is but a dream."
            ),
        ),
        GlossarySong(
            title="The Itsy Bitsy Spider",
            lyrics=(
                "The itsy bitsy spider climbed up the waterspout.\n"
                "Down came the rain and washed the spider out.\n"
                "Out came the sun and dried up all the rain,\n"
                "And the itsy bitsy spider climbed up the spout again."
            ),
        ),
        GlossarySong(
            title="London Bridge Is Falling Down",
            lyrics=(
                "London Bridge is falling down,\n"
                "Falling down, falling down.\n"
                "London Bridge is falling down,\n"
                "My fair lady."
            ),
        ),
        GlossarySong(
            title="Hickory Dickory Dock",
            lyrics=(
                "Hickory dickory dock,\n"
                "The mouse ran up the clock.\n"
                "The clock struck one,\n"
                "The mouse ran down,\n"
                "Hickory dickory dock."
            ),
        ),
        GlossarySong(
            title="Baa, Baa, Black Sheep",
            lyrics=(
                "Baa, baa, black sheep,\n"
                "Have you any wool?\n"
                "Yes sir, yes sir,\n"
                "Three bags full.\n"
                "One for the master,\n"
                "One for the dame,\n"
                "And one for the little boy who lives down the lane."
            ),
        ),
        GlossarySong(
            title="Humpty Dumpty",
            lyrics=(
                "Humpty Dumpty sat on a wall,\n"
                "Humpty Dumpty had a great fall.\n"
                "All the king's horses and all the king's men\n"
                "Couldn't put Humpty together again."
            ),
        ),
        GlossarySong(
            title="Ring Around the Rosie",
            lyrics=(
                "Ring around the rosie,\n"
                "A pocket full of posies.\n"
                "Ashes, ashes,\n"
                "We all fall down."
            ),
        ),
    ],
)


def get_child_age_months(date_of_birth, now: datetime | None = None) -> float:
    """Return child's age in months from date_of_birth (similar to front-end helper)."""
    if not date_of_birth:
        return 0.0
    if now is None:
        now = timezone.now()
    birth = datetime(
        date_of_birth.year,
        date_of_birth.month,
        date_of_birth.day,
        tzinfo=now.tzinfo,
    )
    months = (
        (now.year - birth.year) * 12
        + (now.month - birth.month)
        + (now.day - birth.day) / 31.0
    )
    return max(0.0, months)


def _minutes_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 60.0


def _format_minutes_ago(minutes: float) -> str:
    if minutes < 60:
        return f"{round(minutes)} min ago"
    hours = int(minutes // 60)
    remaining = int(round(minutes % 60))
    if remaining == 0:
        return f"{hours}h ago"
    return f"{hours}h {remaining}m ago"


def _format_fed_detail(
    elapsed_min: float, timeline_events: Iterable[dict] | None
) -> str:
    ago = _format_minutes_ago(elapsed_min)
    if not timeline_events:
        return f"Fed {ago}"
    last_feeding = next(
        (e for e in timeline_events if e.get("type") == "feeding" and e.get("feeding")),
        None,
    )
    if last_feeding and last_feeding.get("feeding"):
        feeding = last_feeding["feeding"]
        ftype = feeding.get("feeding_type")
        amount = feeding.get("amount_oz")
        if ftype == "bottle" and amount is not None:
            return f"Fed {ago} (bottle, {amount}oz)"
        if ftype == "breast":
            return f"Fed {ago} (breast)"
    return f"Fed {ago}"


def _format_diaper_detail(elapsed_min: float) -> str:
    return f"Changed {_format_minutes_ago(elapsed_min)}"


def _format_nap_detail(awake_min: float) -> str:
    return f"Last nap ended {_format_minutes_ago(awake_min)}"


def get_auto_check_state(
    *,
    pattern_alerts: dict | None,
    timeline_events: list[dict] | None,
    child_age_months: float,
    now: datetime | None = None,
) -> AutoCheckState:
    """
    Derive auto-check state from analytics pattern alerts + merged timeline events.
    Mirrors front-end getAutoCheckState behavior.
    """
    if now is None:
        now = timezone.now()

    DEFAULT_FEEDING_INTERVAL_MINUTES = 180
    FED_WARNING_MULTIPLIER = 1.1
    DIAPER_OK_WITHIN_MINUTES = 120

    # Fed
    fed: AutoCheckStatus
    fed_detail: str | None = None
    feeding_pa = (pattern_alerts or {}).get("feeding") if pattern_alerts else None
    if feeding_pa:
        data_points = feeding_pa.get("data_points") or 0
        last_fed_at_iso = feeding_pa.get("last_fed_at")
        if data_points == 0 or not last_fed_at_iso:
            fed = "missing"
        else:
            interval = (
                feeding_pa.get("avg_interval_minutes")
                or DEFAULT_FEEDING_INTERVAL_MINUTES
            )
            last_dt = datetime.fromisoformat(last_fed_at_iso)
            elapsed = float(
                feeding_pa.get("minutes_since_last") or _minutes_between(last_dt, now)
            )
            if elapsed <= interval:
                fed = "ok"
            elif elapsed <= interval * FED_WARNING_MULTIPLIER:
                fed = "warning"
            else:
                fed = "missing"
            fed_detail = _format_fed_detail(elapsed, timeline_events)
    else:
        fed = "missing"

    # Diaper from timeline
    diaper: AutoCheckStatus
    diaper_detail: str | None = None
    if timeline_events:
        diaper_event = next(
            (
                e
                for e in timeline_events
                if e.get("type") == "diaper" and e.get("diaper")
            ),
            None,
        )
        if diaper_event and diaper_event.get("diaper"):
            changed_at = diaper_event["diaper"]["changed_at"]
            if isinstance(changed_at, datetime):
                changed_dt = changed_at
            else:
                changed_dt = datetime.fromisoformat(str(changed_at))
            elapsed_min = _minutes_between(changed_dt, now)
            if elapsed_min <= DIAPER_OK_WITHIN_MINUTES:
                diaper = "ok"
            else:
                diaper = "missing"
            diaper_detail = _format_diaper_detail(elapsed_min)
        else:
            diaper = "missing"
    else:
        diaper = "missing"

    # Nap from pattern alerts
    nap: AutoCheckStatus
    nap_detail: str | None = None
    WAKE_WINDOW_MINUTES: list[tuple[float, int]] = [
        (3, 90),
        (6, 150),
        (12, 210),
        (999, 300),
    ]

    def _wake_window_for_age(months: float) -> int:
        for max_months, minutes in WAKE_WINDOW_MINUTES:
            if months <= max_months:
                return minutes
        return 300

    nap_pa = (pattern_alerts or {}).get("nap") if pattern_alerts else None
    if nap_pa:
        data_points = nap_pa.get("data_points") or 0
        last_nap_ended_iso = nap_pa.get("last_nap_ended_at")
        if data_points == 0 or not last_nap_ended_iso:
            nap = "missing"
        else:
            wake_window = nap_pa.get("avg_wake_window_minutes") or _wake_window_for_age(
                child_age_months
            )
            last_dt = datetime.fromisoformat(last_nap_ended_iso)
            awake_min = float(
                nap_pa.get("minutes_awake") or _minutes_between(last_dt, now)
            )
            nap_detail = _format_nap_detail(awake_min)
            if awake_min <= wake_window:
                nap = "ok"
            elif awake_min <= wake_window * FED_WARNING_MULTIPLIER:
                nap = "warning"
            else:
                nap = "missing"
    else:
        nap = "missing"

    return AutoCheckState(
        fed=fed,
        fed_detail=fed_detail,
        diaper=diaper,
        diaper_detail=diaper_detail,
        nap=nap,
        nap_detail=nap_detail,
    )


def build_checklist_items(
    symptom_id: FussBusSymptomId,
    child_age_months: float,
    auto_check_state: AutoCheckState,
) -> list[ChecklistItem]:
    """
    Build ordered checklist: auto items (fed, diaper, nap) then manual items
    filtered by symptom + age.
    """
    items: list[ChecklistItem] = []

    items.append(
        ChecklistItem(
            id="fed",
            label="Fed recently",
            kind="auto",
            auto_status=auto_check_state.fed,
            detail=auto_check_state.fed_detail
            or (
                "No feedings logged today — check if hungry"
                if auto_check_state.fed == "missing"
                else None
            ),
            interactive=False,
        )
    )
    items.append(
        ChecklistItem(
            id="diaper",
            label="Clean diaper",
            kind="auto",
            auto_status=auto_check_state.diaper,
            detail=auto_check_state.diaper_detail
            or (
                "No diaper changes logged recently"
                if auto_check_state.diaper == "missing"
                else None
            ),
            interactive=False,
        )
    )
    items.append(
        ChecklistItem(
            id="nap",
            label="Nap on schedule",
            kind="auto",
            auto_status=auto_check_state.nap,
            detail=auto_check_state.nap_detail,
            interactive=False,
        )
    )

    for definition in MANUAL_CHECKLIST_DEFS:
        if definition.symptom_ids and symptom_id not in definition.symptom_ids:
            continue
        if definition.age_range and not is_in_age_range(
            child_age_months, definition.age_range
        ):
            continue
        items.append(
            ChecklistItem(
                id=definition.id,
                label=definition.label,
                kind="manual",
                interactive=True,
            )
        )

    return items


def get_developmental_contexts(child_age_months: float) -> list[str]:
    """Return age-matched developmental context strings."""
    return [
        ctx.text
        for ctx in DEVELOPMENTAL_CONTEXTS
        if is_in_age_range(child_age_months, ctx.age_range)
    ]


def prioritize_suggestions(
    *,
    checklist_items: list[ChecklistItem],
    checked_manual_ids: set[str],
    symptom_id: FussBusSymptomId,
    auto_check_state: AutoCheckState,
) -> list[PrioritizedSuggestion]:
    """
    Prioritize:
    - Unchecked auto items (fed/diaper/nap) as high
    - Unchecked manual items as medium
    - Generic soothing toolkit suggestion as low
    """
    suggestions: list[PrioritizedSuggestion] = []

    unchecked_auto_ids: list[str] = []
    if auto_check_state.fed != "ok":
        unchecked_auto_ids.append("fed")
    if auto_check_state.diaper != "ok":
        unchecked_auto_ids.append("diaper")
    if auto_check_state.nap != "ok":
        unchecked_auto_ids.append("nap")

    unchecked_manual_ids: list[str] = [
        item.id
        for item in checklist_items
        if item.kind == "manual" and item.id not in checked_manual_ids
    ]

    if "fed" in unchecked_auto_ids:
        suggestions.append(
            PrioritizedSuggestion(
                text=(
                    f"Baby may be hungry — {auto_check_state.fed_detail}"
                    if auto_check_state.fed_detail
                    else "No recent feeding logged — consider offering a feed."
                ),
                priority="high",
            )
        )
    if "diaper" in unchecked_auto_ids:
        suggestions.append(
            PrioritizedSuggestion(
                text="Check if baby needs a diaper change.",
                priority="high",
            )
        )
    if "nap" in unchecked_auto_ids:
        suggestions.append(
            PrioritizedSuggestion(
                text=(
                    f"Baby may be overtired — {auto_check_state.nap_detail}"
                    if auto_check_state.nap_detail
                    else "Last nap was a while ago — consider offering a nap."
                ),
                priority="high",
            )
        )

    for manual_id in unchecked_manual_ids:
        definition = next(
            (d for d in MANUAL_CHECKLIST_DEFS if d.id == manual_id),
            None,
        )
        if not definition:
            continue
        text = (
            definition.suggestion_text
            if definition.suggestion_text
            else f"Consider: {definition.label}"
        )
        suggestions.append(
            PrioritizedSuggestion(
                text=text,
                priority="medium",
            )
        )

    symptom_label = next(
        (s.label for s in SYMPTOM_TYPES if s.id == symptom_id), "fussiness"
    )
    suggestions.append(
        PrioritizedSuggestion(
            text=f"Try techniques from the Soothing Toolkit below for {symptom_label}.",
            priority="low",
        )
    )

    return suggestions


def get_lullaby_songs() -> list[GlossarySong]:
    """Convenience helper for templates: songs from the Singing glossary entry."""
    entry = FUSS_BUS_GLOSSARY.get("Singing")
    return entry.songs or [] if entry else []
