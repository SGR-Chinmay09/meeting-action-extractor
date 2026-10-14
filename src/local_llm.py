import json
import re
from datetime import date, datetime, timedelta

import requests


LLAMA_API_URL = "http://127.0.0.1:8081/v1/chat/completions"
MODEL_NAME = "local-qwen"


def _extract_json(content: str) -> dict:
    """Parse a JSON object from the model response."""
    content = content.strip()
    content = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        content,
        flags=re.IGNORECASE,
    )

    start = content.find("{")
    end = content.rfind("}")

    if start == -1 or end < start:
        raise ValueError("The model did not return a JSON object.")

    return json.loads(content[start:end + 1])


def _normalize_deadline(deadline, meeting_date: date):
    """
    Convert clear deadlines to ISO format.
    Return an issue for missing or ambiguous deadlines.
    """
    if deadline is None:
        return None, "Deadline not specified"

    text = str(deadline).strip()
    if text.lower() in {
        "", "none", "null", "unknown", "n/a",
        "not specified", "not mentioned",
    }:
        return None, "Deadline not specified"

    lowered = text.lower()
    lowered = re.sub(r"\s+", " ", lowered).strip()
    lowered = re.sub(r"^(by|on|before)\s+", "", lowered)

    # Already an ISO date.
    try:
        return date.fromisoformat(text).isoformat(), None
    except ValueError:
        pass

    # Explicit dates such as October 17, 2026.
    for fmt in (
        "%B %d, %Y", "%b %d, %Y",
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y",
        "%B %d", "%b %d", "%d %B", "%d %b",
    ):
        try:
            parsed = datetime.strptime(text, fmt).date()

            if "%Y" not in fmt:
                parsed = parsed.replace(year=meeting_date.year)
                if parsed < meeting_date:
                    parsed = parsed.replace(
                        year=meeting_date.year + 1
                    )

            return parsed.isoformat(), None
        except ValueError:
            continue

    if lowered == "today":
        return meeting_date.isoformat(), None

    if lowered == "tomorrow":
        return (meeting_date + timedelta(days=1)).isoformat(), None

    if lowered == "day after tomorrow":
        return (meeting_date + timedelta(days=2)).isoformat(), None

    # "Next Monday" means the upcoming Monday after the meeting date.
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    weekday_text = lowered.removeprefix("next ").strip()

    if weekday_text in weekdays:
        target_weekday = weekdays[weekday_text]
        days_ahead = (target_weekday - meeting_date.weekday()) % 7

        # "Next Monday" means the following week's Monday,
        # even if the meeting itself is on Monday.
        if lowered.startswith("next ") and days_ahead == 0:
            days_ahead = 7
        

        resolved = meeting_date + timedelta(days=days_ahead)
        return resolved.isoformat(), None

    if lowered in {"this week", "next week", "sometime next week",
                   "later next week", "this weekend", "next weekend",
                   "soon", "later"}:
        return text, f"Ambiguous deadline: '{text}' needs an exact date"

    # Handle phrases like "in 3 days" or "within 2 weeks".
    relative_match = re.fullmatch(
        r"(?:in|within)\s+(\d+)\s+(day|days|week|weeks)",
        lowered,
    )
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        days = amount * (7 if unit.startswith("week") else 1)
        return (meeting_date + timedelta(days=days)).isoformat(), None

    return text, f"Deadline could not be normalized: '{text}'"


def _estimate_confidence(task: str, owner, deadline, issues: list) -> float:
    """Estimate extraction quality using transparent heuristic rules."""

    score = 0.95
    task_text = str(task or "").strip()
    owner_text = str(owner or "").strip().lower()

    if len(task_text) < 5:
        score -= 0.30

    if not any(word in task_text.lower() for word in (
        "prepare", "send", "create", "complete", "test",
        "review", "schedule", "update", "submit", "fix",
        "develop", "check", "share", "deliver"
    )):
        score -= 0.10

    if not owner_text or owner_text in {
        "none", "null", "unknown", "unassigned", "n/a"
    }:
        score -= 0.20

    if not deadline:
        score -= 0.15

    for issue in issues:
        text = str(issue).lower()

        if "ambiguous deadline" in text:
            score -= 0.20
        elif "deadline not specified" in text:
            score -= 0.10
        elif "owner not identified" in text:
            score -= 0.10
        elif "could not be normalized" in text:
            score -= 0.20
        else:
            score -= 0.05

    return round(max(0.10, min(0.95, score)), 2)

def extract_actions_with_llm(
    transcript: str,
    meeting_date: str | None = None,
) -> list:
    """Extract, normalize, and validate meeting action items."""

    if not isinstance(transcript, str) or not transcript.strip():
        return []

    try:
        reference_date = (
            date.fromisoformat(meeting_date)
            if meeting_date
            else date.today()
        )
    except ValueError as exc:
        raise ValueError(
            "meeting_date must use YYYY-MM-DD format"
        ) from exc

    prompt = f"""
Extract actionable tasks from the meeting transcript.

Return ONLY valid JSON:
{{
  "actions": [
    {{
      "task": "Concise task description",
      "owner": "Responsible person's name or null",
      "deadline": "Exact or original deadline phrase, or null"
    }}
  ]
}}

Rules:
- Extract only tasks explicitly supported by the transcript.
- Assign ownership to the person committing to perform the task.
- Resolve "I will do that" using the conversation context.
- Keep the task separate from its deadline.
- Preserve the original deadline wording.
- Do not invent missing owners, dates, or tasks.
- Do not duplicate tasks.
- Return JSON only, without Markdown.

Meeting date: {reference_date.isoformat()}

Transcript:
{transcript}
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract meeting action items accurately. "
                    "Return one JSON object with an actions array. "
                    "Never invent missing information."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 768,
    }

    try:
        response = requests.post(
            LLAMA_API_URL,
            json=payload,
            timeout=180,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]
        actions = _extract_json(content).get("actions", [])

        if not isinstance(actions, list):
            raise ValueError("The model did not return an actions list.")

        cleaned_actions = []
        seen_tasks = set()

        for action in actions:
            if not isinstance(action, dict):
                continue

            task = re.sub(
                r"\s+", " ", str(action.get("task") or "")
            ).strip()

            if len(task) < 5:
                continue

            task_key = task.casefold()
            if task_key in seen_tasks:
                continue
            seen_tasks.add(task_key)

            owner_value = action.get("owner")
            owner = (
                str(owner_value).strip()
                if owner_value is not None
                and str(owner_value).strip().lower()
                not in {"", "none", "null", "unknown", "unassigned", "n/a"}
                else None
            )

            deadline, deadline_issue = _normalize_deadline(
                action.get("deadline"), reference_date
            )

            issues = []

            if owner is None:
                issues.append("Owner not identified")

            if deadline_issue:
                issues.append(deadline_issue)
                if deadline is None and not deadline_issue:
                    issues.append("deadline not specified")

            # Flag deadlines that precede the meeting date.
            if deadline:
                try:
                    parsed_date = date.fromisoformat(deadline)
                    if parsed_date < reference_date:
                        issues.append(
                            "Deadline is before the meeting date"
                        )
                except ValueError:
                    # An unresolved phrase is already flagged above.
                    pass

            confidence = _estimate_confidence(
                task, owner, deadline, issues
            )

            cleaned_actions.append({
                "task": task,
                "owner": owner,
                "deadline": deadline,
                "status": "Pending",
                "confidence": confidence,
                "needs_review": bool(issues) or deadline is None or confidence< 0.70 ,
                "validation_issues": issues,
            })

        return cleaned_actions

    except (
        requests.RequestException,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
    ) as error:
        raise RuntimeError(
            f"Local AI extraction failed: {error}"
        ) from error