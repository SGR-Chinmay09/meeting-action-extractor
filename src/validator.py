import re
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher


MISSING_VALUES = {
    "", "unknown", "unassigned", "none", "null",
    "n/a", "not specified", "not set", "tbd"
}

MONTHS = (
    "January February March April May June "
    "July August September October November December"
).split()


def _parse_deadline(value, reference_date):
    """
    Return (ISO date or None, issue or None).

    Converts only dates that can be interpreted reliably.
    Ambiguous phrases are flagged rather than guessed.
    """
    if value is None:
        return None, "Deadline not specified"

    text = str(value).strip()
    if text.lower() in MISSING_VALUES:
        return None, "Deadline not specified"

    normalized = re.sub(r"\s+", " ", text).strip()
    lower = normalized.lower()

    # Relative dates.
    if lower in {"today", "tonight"}:
        return reference_date.isoformat(), None

    if lower == "tomorrow":
        return (reference_date + timedelta(days=1)).isoformat(), None

    if lower == "day after tomorrow":
        return (reference_date + timedelta(days=2)).isoformat(), None

    match = re.fullmatch(r"in\s+(\d+)\s+days?", lower)
    if match:
        days = int(match.group(1))
        return (reference_date + timedelta(days=days)).isoformat(), None

    match = re.fullmatch(r"within\s+(\d+)\s+days?", lower)
    if match:
        days = int(match.group(1))
        return (reference_date + timedelta(days=days)).isoformat(), None

    # Weekday phrases: "Friday", "by Monday", or "next Friday".
    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2,
        "thursday": 3, "friday": 4, "saturday": 5,
        "sunday": 6,
    }

    weekday_match = re.fullmatch(
        r"(?:by\s+|on\s+|next\s+)?"
        r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        lower,
    )

    if weekday_match:
        weekday_name = weekday_match.group(1)
        target_weekday = weekdays[weekday_name]
        days_ahead = (target_weekday - reference_date.weekday()) % 7

        # "Next Friday" means the Friday in the following week.
        if lower.startswith("next "):
            days_ahead = days_ahead + 7 if days_ahead < 7 else days_ahead

        # A bare weekday that is today means the next occurrence,
        # not a past deadline.
        if days_ahead == 0:
            days_ahead = 7

        return (
            reference_date + timedelta(days=days_ahead)
        ).isoformat(), None

    # "Next week" does not identify an exact day.
    if re.search(r"\bnext week\b|\bsometime next week\b", lower):
        return None, (
            "Ambiguous deadline: 'next week' needs an exact date"
        )

    if re.search(r"\bsoon\b|\bwhen possible\b|\basap\b", lower):
        return None, (
            "Deadline is vague; confirm the exact date"
        )

    # Explicit numeric dates.
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            parsed = datetime.strptime(normalized, fmt).date()
            return parsed.isoformat(), None
        except ValueError:
            pass

    # Month names with an optional year, e.g. "October 17".
    for fmt in (
        "%B %d, %Y", "%B %d %Y",
        "%b %d, %Y", "%b %d %Y",
        "%d %B %Y", "%d %b %Y",
        "%B %d", "%b %d", "%d %B", "%d %b",
    ):
        try:
            parsed = datetime.strptime(normalized, fmt).date()

            # If no year was supplied, use the meeting year.
            if "%Y" not in fmt:
                parsed = parsed.replace(year=reference_date.year)

                # If that date has passed, do not silently assume
                # the following year; flag it for human review.
                if parsed < reference_date:
                    return None, (
                        "Deadline may refer to another year; confirm it"
                    )

            return parsed.isoformat(), None
        except ValueError:
            pass

    return None, f"Could not interpret deadline: '{normalized}'"


def _task_similarity(first, second):
    """Compare task descriptions while ignoring simple punctuation."""
    first = re.sub(r"[^a-z0-9\s]", " ", first.lower())
    second = re.sub(r"[^a-z0-9\s]", " ", second.lower())

    first = re.sub(r"\s+", " ", first).strip()
    second = re.sub(r"\s+", " ", second).strip()

    if not first or not second:
        return 0.0

    return SequenceMatcher(None, first, second).ratio()


def _confidence_score(task, owner, deadline, issues, item):
    """
    Produce a transparent heuristic score between 0 and 1.

    This is not a calibrated probability that the extraction is correct.
    """
    score = 0.40

    # Task description quality.
    if len(task) >= 10:
        score += 0.20
    elif len(task) >= 5:
        score += 0.10

    # A named owner improves action-item completeness.
    if owner:
        score += 0.15

    # A successfully interpreted deadline is useful evidence.
    if deadline:
        score += 0.15

    # Reduce confidence for specific validation concerns.
    penalties = {
        "Deadline not specified": 0.10,
        "Owner not identified": 0.10,
        "Task description is too short": 0.15,
        "Missing task description": 0.25,
    }

    for issue in issues:
        score -= penalties.get(issue, 0.0)

        if "Ambiguous deadline" in issue:
            score -= 0.15
        elif "Could not interpret deadline" in issue:
            score -= 0.15
        elif "confirm" in issue.lower():
            score -= 0.10
        elif "duplicate" in issue.lower():
            score -= 0.10

    # Use a model-supplied confidence only as a small, bounded signal.
    # Do not treat it as ground truth.
    supplied = item.get("confidence")
    if supplied is not None:
        try:
            supplied = float(supplied)
            if supplied > 1:
                supplied /= 100
            supplied = max(0.0, min(1.0, supplied))
            score = (score * 0.85) + (supplied * 0.15)
        except (TypeError, ValueError):
            pass

    return round(max(0.0, min(1.0, score)), 2)


def validate_action_items(
    action_items: list,
    meeting_date: str | None = None,
) -> list:
    """
    Validate task descriptions, owners, deadlines, confidence,
    and duplicate action items.
    """
    if meeting_date:
        try:
            reference_date = date.fromisoformat(meeting_date)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "meeting_date must use YYYY-MM-DD format"
            ) from exc
    else:
        reference_date = date.today()

    results = []

    for item in action_items:
        if not isinstance(item, dict):
            continue

        checked = item.copy()
        issues = []

        # 1. Task validation.
        task = str(checked.get("task") or "").strip()
        checked["task"] = task

        if not task:
            issues.append("Missing task description")
        elif len(task) < 5:
            issues.append("Task description is too short")

        # 2. Owner validation.
        raw_owner = checked.get("owner")
        owner_text = str(raw_owner or "").strip()

        if owner_text.lower() in MISSING_VALUES:
            owner = None
            issues.append("Owner not identified")
        else:
            owner = owner_text

        checked["owner"] = owner

        # 3. Deadline validation and normalization.
        raw_deadline = checked.get("deadline")
        deadline, deadline_issue = _parse_deadline(
            raw_deadline, reference_date
        )

        checked["deadline"] = deadline

        if deadline_issue:
            issues.append(deadline_issue)

        if deadline:
            parsed_deadline = date.fromisoformat(deadline)
            if parsed_deadline < reference_date:
                issues.append("Deadline is before the meeting date")

        # 4. Status validation.
        allowed_statuses = {"Pending", "In Progress", "Completed"}
        status = str(checked.get("status") or "Pending").strip()

        if status not in allowed_statuses:
            status = "Pending"

        checked["status"] = status

        # 5. Preserve existing extraction metadata, if present.
        checked["confidence"] = _confidence_score(
            task, owner, deadline, issues, item
        )
        checked["validation_issues"] = issues
        checked["needs_review"] = bool(issues) or (
            checked["confidence"] < 0.60
        )

        results.append(checked)

    # 6. Flag near-duplicate tasks.
    for index, current in enumerate(results):
        current_task = str(current.get("task") or "")

        for previous in results[:index]:
            previous_task = str(previous.get("task") or "")

            if _task_similarity(current_task, previous_task) >= 0.85:
                issue = "Possible duplicate task"

                if issue not in current["validation_issues"]:
                    current["validation_issues"].append(issue)

                current["needs_review"] = True
                current["confidence"] = round(
                    max(0.0, current["confidence"] - 0.10), 2
                )
                break

    return results