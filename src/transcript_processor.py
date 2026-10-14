import re


def clean_transcript(transcript: str) -> str:
    """Clean whitespace and formatting from a meeting transcript."""
    if not transcript or not transcript.strip():
        return ""

    # Normalize line endings
    transcript = transcript.replace("\r\n", "\n").replace("\r", "\n")

    # Remove unnecessary spaces
    lines = [line.strip() for line in transcript.split("\n")]

    # Remove empty lines and join the remaining lines
    transcript = "\n".join(line for line in lines if line)

    # Normalize repeated spaces within each line
    transcript = re.sub(r"[ \t]+", " ", transcript)

    return transcript


def segment_transcript(transcript: str) -> list:
    """Split the transcript into speaker-labelled segments."""
    cleaned = clean_transcript(transcript)
    segments = []

    for line in cleaned.split("\n"):
        match = re.match(r"^([^:\n]+):\s*(.+)$", line)

        if match:
            segments.append({
                "speaker": match.group(1).strip(),
                "text": match.group(2).strip()
            })
        else:
            segments.append({
                "speaker": "Unknown",
                "text": line
            })

    return segments