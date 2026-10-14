import re
from datetime import date, datetime, timedelta
from typing import Optional


ACTION_VERBS = (
    "prepare", "create", "finish", "complete", "submit",
    "send", "share", "test", "review", "schedule",
    "organize", "update", "fix", "develop", "design",
    "implement", "check", "report", "collect", "present",
    "write", "build", "deploy", "verify", "finalize",
    "discuss", "arrange", "deliver", "publish", "analyze",
    "analyse", "confirm", "contact", "call", "email",
    "upload", "download", "research", "document", "resolve",
)

MONTHS = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)


def _parse_meeting_date(meeting_date: Optional[str]):
    """Parse an ISO meeting date, if one was supplied."""
    if not meeting_date:
        return None

    try:
        return date.fromisoformat(meeting_date)
    except (TypeError, ValueError):
        return None


def extract_deadline(
    text: str,
    meeting_date: Optional[str] = None,
) -> Optional[str]:
    """Extract an explicit deadline or preserve relative wording."""
    if not text:
        return None

    # October 17, Oct 17, October 17th
    month_pattern = (
        r"\b(" + MONTHS + r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|"
        r"Sep|Sept|Oct|Nov|Dec)"
        r"\s+\d{1,2}(?:st|nd|rd|th)?"
        r"(?:,?\s+\d{4})?\b"
    )

    match = re.search(month_pattern, text, re.IGNORECASE)
    if match:
        return match.group(0).strip()

    # 17 October, 17th October
    match = re.search(
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+"
        r"(?:" + MONTHS + r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|"
        r"Sep|Sept|Oct|Nov|Dec)"
        r"(?:\s+\d{4})?\b",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(0).strip()

    # ISO date: 2026-10-17
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if match:
        return match.group(0)

    # Numeric dates: 17/10/2026 or 17-10-2026
    match = re.search(
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b",
        text,
    )
    if match:
        return match.group(0)

    # Relative deadlines should remain visible for human review.
    relative_patterns = [
        r"\bnext week\b",
        r"\bthis week\b",
        r"\bby tomorrow\b",
        r"\btomorrow\b",
        r"\btoday\b",
        r"\bby Friday\b",
        r"\bby Monday\b",
        r"\bby Tuesday\b",
        r"\bby Wednesday\b",
        r"\bby Thursday\b",
        r"\bby Saturday\b",
        r"\bby Sunday\b",
        r"\bnext month\b",
        r"\bwithin \d+ days?\b",
        r"\bin \d+ days?\b",
    ]

    for pattern in relative_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    # A meeting date is intentionally not used to invent a deadline.
    return None


def _clean_task(text: str) -> str:
    """Remove simple conversational prefixes and surrounding punctuation."""
    task = text.strip()

    task = re.sub(
        r"^(?:please\s+|can you\s+|could you\s+|"
        r"we need to\s+|you should\s+|"
        r"i will\s+|i'll\s+|we will\s+|we'll\s+)",
        "",
        task,
        flags=re.IGNORECASE,
    )

    task = re.sub(r"\s+", " ", task)
    return task.strip(" \t\r\n.,;:-")


def _estimate_confidence(
    text: str,
    owner: Optional[str],
    deadline: Optional[str],
    action_match: bool,
) -> float:
    """
    Return a heuristic score from 0 to 1.
    This is not a calibrated probability.
    """
    score = 0.35

    if action_match:
        score += 0.25

    if len(text.split()) >= 4:
        score += 0.10

    if owner and owner.strip().lower() not in {
        "unknown", "none", "unassigned", "speaker"
    }:
        score += 0.15

    if deadline:
        score += 0.15

    return round(min(score, 0.95), 2)


def extract_action_items(
    segments: list,
    meeting_date: Optional[str] = None,
) -> list:
    """
    Extract likely action items from speaker-labelled transcript segments.

    Expected segment format:
        {"speaker": "Rahul", "text": "Prepare the slides by October 17."}

    Returns dictionaries with:
        task, owner, deadline, status, confidence
    """
    action_items = []
    reference_date = _parse_meeting_date(meeting_date)

    for segment in segments:
        if not isinstance(segment, dict):
            continue

        speaker = str(segment.get("speaker", "Unknown")).strip()
        text = str(segment.get("text", "")).strip()

        if not text:
            continue

        # Split transcript segments into individual statements.
        statements = re.split(r"(?<=[.!?])\s+|\n+", text)

        for statement in statements:
            statement = statement.strip()
            if not statement:
                continue

            lower_text = statement.lower()

            # Avoid treating questions about possible future tasks as commitments.
            suggestion = bool(
                re.search(
                    r"\b(?:should we|could we|can we|"
                    r"what if we|maybe we should|"
                    r"we could consider)\b",
                    lower_text,
                )
            )

            action_match = re.search(
                r"\b(?:" + "|".join(ACTION_VERBS) + r")\b",
                lower_text,
            )

            # Capture explicit commitments even if phrased as "I will..."
            self_commitment = bool(
                re.search(
                    r"\b(?:i will|i'll|i can|i am going to|"
                    r"we will|we'll|we are going to)\b",
                    lower_text,
                )
            )

            if not action_match and not self_commitment:
                continue

            # Ignore uncertain suggestions as confirmed commitments.
            task = _clean_task(statement)
            if not task:
                continue

            deadline = extract_deadline(statement, meeting_date)

            # Remove deadline wording from the task description.
            if deadline:
                task = re.sub(
                    re.escape(deadline),
                    "",
                    task,
                    flags=re.IGNORECASE,
                )
                task = re.sub(
                    r"\b(?:by|before|on|due)\s*$",
                    "",
                    task,
                    flags=re.IGNORECASE,
                )
                task = re.sub(r"\s+", " ", task).strip(" .,;:-")

            if not task:
                continue

            # Use the speaker as owner only for explicit first-person commitments.
            explicit_self = bool(
                re.search(
                    r"\b(?:i will|i'll|i can|i am going to)\b",
                    lower_text,
                )
            )

            owner = (
                speaker
                if explicit_self and speaker.lower() != "unknown"
                else None
            )

            # Recognize a named person assigned the work.
            assigned_match = re.search(
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
                r"\s+(?:will|should|must|needs to|has to)\s+"
                r"(?:" + "|".join(ACTION_VERBS) + r")\b",
                statement,
            )

            if assigned_match:
                owner = assigned_match.group(1).strip()

            # "Rahul, please prepare the slides" pattern.
            if not owner:
                assigned_match = re.search(
                    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
                    r"\s*,\s*(?:please\s+)?"
                    r"(?:" + "|".join(ACTION_VERBS) + r")\b",
                    statement,
                )
                if assigned_match:
                    owner = assigned_match.group(1).strip()

            # Convert clear relative deadlines to ISO dates when possible.
            if deadline and reference_date:
                relative = deadline.lower()

                if relative == "today":
                    deadline = reference_date.isoformat()
                elif relative == "tomorrow" or relative == "by tomorrow":
                    deadline = (
                        reference_date + timedelta(days=1)
                    ).isoformat()

            confidence = _estimate_confidence(
                statement,
                owner,
                deadline,
                bool(action_match or self_commitment),
            )

            needs_review = (
                suggestion
                or owner is None
                or deadline is None
                or confidence < 0.65
            )

            status = "Needs review" if needs_review else "Pending"

            item = {
                "task": task,
                "owner": owner,
                "deadline": deadline,
                "status": status,
                "confidence": confidence,
            }

            # Avoid exact duplicate tasks.
            duplicate = any(
                existing["task"].lower() == task.lower()
                and (existing.get("owner") or "").lower()
                == (owner or "").lower()
                for existing in action_items
            )

            if not duplicate:
                action_items.append(item)

    return action_items

