import json
from pathlib import Path

import pandas as pd


COLUMNS = [
    "task",
    "owner",
    "deadline",
    "status",
    "confidence"
]


def create_action_table(action_items: list) -> pd.DataFrame:
    """Convert extracted action items into a structured table."""
    df = pd.DataFrame(action_items, columns=COLUMNS)

    if df.empty:
        return df

    # Represent missing information explicitly.
    df["owner"] = df["owner"].fillna("Unassigned")
    df["deadline"] = df["deadline"].fillna("Not specified")

    # Make confidence easier to interpret.
    df["confidence_percent"] = (
        df["confidence"].astype(float) * 100
    ).round(1)

    return df


def export_action_items(
    action_items: list,
    output_path: str = "data/action_items.json"
) -> None:
    """Export action items as readable JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            action_items,
            file,
            indent=4,
            ensure_ascii=False
        )


if __name__ == "__main__":
    from src.transcript_processor import segment_transcript
    from src.action_extractor import extract_action_items

    transcript_path = Path("data/sample_transcript.txt")
    transcript = transcript_path.read_text(encoding="utf-8")

    segments = segment_transcript(transcript)
    items = extract_action_items(segments)

    table = create_action_table(items)

    print("\nEXTRACTED ACTION ITEMS\n")
    print(table.to_string(index=False))

    export_action_items(items)
    print("\nJSON saved to data/action_items.json")