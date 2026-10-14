import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.transcript_processor import segment_transcript
from src.action_extractor import extract_action_items
from src.validator import validate_action_items
from src.local_llm import extract_actions_with_llm


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="AI Meeting Action Extractor",
    page_icon="📋",
    layout="wide",
)

st.title("📋 AI Meeting Action-Item Extractor")
st.caption(
    "Convert meeting transcripts into structured, reviewable tasks."
)


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

sample_path = Path("data/sample_transcript.txt")

if "transcript" not in st.session_state:
    st.session_state.transcript = (
        sample_path.read_text(encoding="utf-8")
        if sample_path.exists()
        else ""
    )

if "results" not in st.session_state:
    st.session_state.results = None


# --------------------------------------------------
# 1. MEETING TRANSCRIPT
# --------------------------------------------------

st.subheader("1. Meeting transcript")

transcript = st.text_area(
    "Paste your transcript below",
    key="transcript",
    height=250,
    placeholder=(
        "Example: Rahul: I will prepare the slides by October 17."
    ),
)

meeting_date = st.date_input(
    "Meeting date (used to review relative deadlines)",
    value=pd.Timestamp.today().date(),
)

if st.button("Extract action items", type="primary"):
    if not transcript.strip():
        st.warning("Please enter a meeting transcript.")
    else:
        try:
            with st.spinner("Extracting and validating action items..."):
                # Use the local Qwen model.
                items = extract_actions_with_llm(transcript,meeting_date=meeting_date.isoformat(),)

                # Validate the extracted results.
                validated_items = validate_action_items(
                    items,
                    meeting_date=meeting_date.isoformat(),
                )

            st.session_state.results = validated_items

            if not validated_items:
                st.info("No action items were identified.")

        except Exception as exc:
            st.error(f"Could not process the transcript: {exc}")


# --------------------------------------------------
# 2. EXTRACTED ACTION ITEMS
# --------------------------------------------------

if st.session_state.results is not None:
    validated_items = st.session_state.results

    st.divider()
    st.subheader("2. Extracted action items")
    st.caption(
        "Review and edit the extracted fields before downloading. "
        "Confidence is a heuristic score, not a calibrated probability."
    )

    df = pd.DataFrame(validated_items)

    expected_columns = [
        "task",
        "owner",
        "deadline",
        "status",
        "confidence",
        "needs_review",
        "validation_issues",
    ]

    # Ensure all expected columns exist.
    for column in expected_columns:
        if column not in df.columns:
            if column == "validation_issues":
                df[column] = [[] for _ in range(len(df))]
            elif column == "needs_review":
                df[column] = False
            elif column == "confidence":
                df[column] = 0.0
            elif column == "status":
                df[column] = "Pending"
            else:
                df[column] = "None"

    # Preserve additional columns.
    df = df[
        expected_columns
        + [
            column
            for column in df.columns
            if column not in expected_columns
        ]
    ]

    display_df = df.copy()

    # Display validation issues as readable text.
    display_df["validation_issues"] = display_df[
        "validation_issues"
    ].apply(
        lambda value: (
            "; ".join(map(str, value))
            if isinstance(value, list)
            else str(value or "")
        )
    )

    # Normalize confidence values.
    display_df["confidence"] = pd.to_numeric(
        display_df["confidence"],
        errors="coerce",
    ).fillna(0.0)

    # Convert decimal confidence values to percentages.
    if not display_df.empty:
        display_df["confidence"] = display_df["confidence"].apply(
            lambda value: round(value * 100, 1)
            if 0 < value <= 1
            else round(value, 1)
        )

    # Editable action-item table.
    edited_df = st.data_editor(
        display_df,
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "task": st.column_config.TextColumn("Task"),
            "owner": st.column_config.TextColumn("Owner"),
            "deadline": st.column_config.TextColumn("Deadline"),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=[
                    "Pending",
                    "In Progress",
                    "Completed",
                ],
            ),
            "confidence": st.column_config.NumberColumn(
                "Confidence (%)",
                min_value=0,
                max_value=100,
                step=1,
            ),
            "needs_review": st.column_config.CheckboxColumn(
                "Needs review"
            ),
            "validation_issues": st.column_config.TextColumn(
                "Validation issues",
                disabled=True,
            ),
        },
        key="action_item_editor",
    )

    # --------------------------------------------------
    # 3. SUMMARY METRICS
    # --------------------------------------------------

    st.divider()
    st.subheader("Summary")

    total_items = len(edited_df)

    owners = (
        edited_df["owner"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    assigned_tasks = (~owners.isin([
        "",
        "none",
        "unknown",
        "unassigned",
        "nan",
    ])).sum()

    needs_review_count = (
        edited_df["needs_review"]
        .fillna(False)
        .astype(bool)
        .sum()
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Total action items", total_items)
    col2.metric("Assigned tasks", int(assigned_tasks))
    col3.metric("Needs review", int(needs_review_count))

    # --------------------------------------------------
    # 4. VALIDATION WARNINGS
    # --------------------------------------------------

    st.divider()
    st.subheader("3. Validation warnings")

    has_warnings = False

    for index, row in edited_df.iterrows():
        raw_issues = row.get("validation_issues", "")

        if isinstance(raw_issues, list):
            issues = [
                str(issue).strip()
                for issue in raw_issues
                if str(issue).strip()
            ]
        else:
            issues = [
                issue.strip()
                for issue in str(raw_issues or "").split(";")
                if issue.strip()
            ]

        if issues:
            has_warnings = True
            st.warning(
                f"Task {index + 1}: " + ", ".join(issues)
            )

    if not has_warnings:
        st.success("No validation warnings found.")

    # --------------------------------------------------
    # 5. JSON EXPORT
    # --------------------------------------------------

    st.divider()
    st.subheader("4. Export")

    export_df = edited_df.copy()

    export_df["confidence"] = pd.to_numeric(
        export_df["confidence"],
        errors="coerce",
    ).fillna(0)

    # Convert missing values to JSON null.
    export_df = export_df.astype(object).where(
        pd.notna(export_df),
        None,
    )

    records = export_df.to_dict(orient="records")

    # Convert validation issue text back to a JSON list.
    for record in records:
        issues = record.get("validation_issues", "")

        if isinstance(issues, str):
            record["validation_issues"] = [
                issue.strip()
                for issue in issues.split(";")
                if issue.strip()
            ]

    json_output = json.dumps(
        records,
        indent=4,
        ensure_ascii=False,
        default=str,
    )

    st.download_button(
        label="Download action items as JSON",
        data=json_output,
        file_name="action_items.json",
        mime="application/json",
    )