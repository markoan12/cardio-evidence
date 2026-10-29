import os
import json
import time
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

from screening_prompt import SYSTEM_PROMPT, SCREENING_SCHEMA


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")

DEFAULT_INPUT = "publications.csv"

RESULTS_FILE = Path("screening_history.jsonl")
OVERRIDES_FILE = Path("screening_overrides.csv")

APPROVED_FILE = Path("approved_publications.csv")
REVIEW_FILE = Path("ai_review_queue.csv")
EXCLUDED_FILE = Path("excluded_publications.csv")

PROMPT_VERSION = hashlib.sha256(
    (
        SYSTEM_PROMPT
        + json.dumps(SCREENING_SCHEMA, sort_keys=True)
    ).encode("utf-8")
).hexdigest()[:12]

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    timeout=90.0,
    max_retries=2,
)

VALID_DECISIONS = {"Approve", "Review", "Exclude"}

ELIGIBLE_DESIGNS = {
    "Randomized Controlled Trial",
    "Observational Study",
    "Guideline or Statement",
}

ELIGIBLE_RELEVANCE = {
    "Core Cardiovascular",
    "Cardiovascular Related",
}


# ============================================================
# LOAD SCREENING HISTORY
# ============================================================

def load_history():

    history = {}

    if not RESULTS_FILE.exists():
        return history

    with RESULTS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        for line in file:

            if not line.strip():
                continue

            record = json.loads(line)

            key = (
                str(record["PMID"]),
                record["model"],
                record["prompt_version"],
                record["source_hash"],
            )

            history[key] = record

    return history


# ============================================================
# ARTICLE CONTENT HASH
# ============================================================

def article_hash(row):

    content = {
        "Title": row.get("Title", ""),
        "Abstract": row.get("Abstract", ""),
        "Publication Types": row.get(
            "Publication Types", ""
        ),
        "Journal": row.get("Journal", ""),
    }

    encoded = json.dumps(
        content,
        sort_keys=True,
        ensure_ascii=False
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()[:16]


# ============================================================
# AI SCREENING
# ============================================================

def screen_article(row):

    article = {
        "pmid": str(row.get("PMID", "")),
        "title": row.get("Title", ""),
        "abstract": row.get("Abstract", ""),
        "publication_types": row.get(
            "Publication Types", ""
        ),
        "journal": row.get("Journal", ""),
    }

    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=json.dumps(
            article,
            ensure_ascii=False
        ),
        text={
            "format": {
                "type": "json_schema",
                "name": "cardioevidence_screening",
                "strict": True,
                "schema": SCREENING_SCHEMA,
            }
        },
        max_output_tokens=800,
    )

    if (
        response.status != "completed"
        or not response.output_text
    ):
        raise RuntimeError(
            f"Incomplete response: {response.status}"
        )

    result = json.loads(response.output_text)

    if result["decision"] not in VALID_DECISIONS:
        raise ValueError("Invalid screening decision")

    if not 1 <= result["clinical_priority"] <= 5:
        raise ValueError("Invalid clinical priority")

    # Prevent approval of an ineligible study.
    if result["decision"] == "Approve":

        if (
            result["study_design"] not in ELIGIBLE_DESIGNS
            or result["relevance"] not in ELIGIBLE_RELEVANCE
        ):

            result["decision"] = "Review"

            result["reason"] += (
                " [Automatic approval blocked.]"
            )

    return result


# ============================================================
# SAVE EACH RESULT
# ============================================================

def save_result(record):

    with RESULTS_FILE.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            json.dumps(
                record,
                ensure_ascii=False
            ) + "\n"
        )

        file.flush()
        os.fsync(file.fileno())


# ============================================================
# MANUAL OVERRIDES
# ============================================================

def load_overrides():

    if not OVERRIDES_FILE.exists():
        return {}

    df = pd.read_csv(
        OVERRIDES_FILE,
        dtype=str
    ).fillna("")

    required = {"PMID", "decision"}

    if not required.issubset(df.columns):
        raise ValueError(
            "Overrides file needs PMID and decision columns."
        )

    if df["PMID"].duplicated().any():
        raise ValueError(
            "Duplicate PMIDs in screening_overrides.csv"
        )

    if not df["decision"].isin(VALID_DECISIONS).all():
        raise ValueError(
            "Invalid manual override decision"
        )

    return dict(
        zip(df["PMID"], df["decision"])
    )


# ============================================================
# EXPORT PUBLICATION DATABASES
# ============================================================

def export_results(df, history):

    overrides = load_overrides()

    rows = []

    for _, row in df.iterrows():

        pmid = str(row["PMID"])
        source_hash = article_hash(row)

        key = (
            pmid,
            MODEL,
            PROMPT_VERSION,
            source_hash,
        )

        record = history.get(key)

        if record is None:
            continue

        combined = row.to_dict()

        for field in [
            "relevance",
            "study_design",
            "subspecialty",
            "clinical_priority",
            "reason",
        ]:
            combined[field] = record[field]

        combined["AI Decision"] = record["decision"]

        combined["Final Decision"] = overrides.get(
            pmid,
            record["decision"]
        )

        combined["Decision Source"] = (
            "Manual Override"
            if pmid in overrides
            else "AI"
        )

        combined["AI Model"] = record["model"]

        combined["Prompt Version"] = (
            record["prompt_version"]
        )

        combined["Screened At"] = (
            record["screened_at"]
        )

        rows.append(combined)

    if not rows:
        print("No completed screenings to export.")
        return

    results = pd.DataFrame(rows)

    approved = results[
        results["Final Decision"] == "Approve"
    ]

    review = results[
        results["Final Decision"] == "Review"
    ]

    excluded = results[
        results["Final Decision"] == "Exclude"
    ]

    approved.to_csv(
        APPROVED_FILE,
        index=False
    )

    review.to_csv(
        REVIEW_FILE,
        index=False
    )

    excluded.to_csv(
        EXCLUDED_FILE,
        index=False
    )

    print("\n========== RESULTS ==========")

    print(f"Screened: {len(results)}")
    print(f"Approved: {len(approved)}")
    print(f"Review: {len(review)}")
    print(f"Excluded: {len(excluded)}")

    print("=============================")


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT
    )

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--limit",
        type=int,
        default=100
    )

    group.add_argument(
        "--all",
        action="store_true"
    )

    parser.add_argument(
        "--export-only",
        action="store_true"
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    df = pd.read_csv(
        args.input,
        dtype=str
    ).fillna("")

    if "PMID" not in df.columns:
        raise ValueError("Input CSV must contain PMID")

    df = df[
        df["PMID"].str.strip() != ""
    ].drop_duplicates(
        subset=["PMID"],
        keep="last"
    )

    history = load_history()

    print("\nCardioEvidence AI Screening")
    print("--------------------------")

    print("Model:", MODEL)
    print("Prompt version:", PROMPT_VERSION)
    print("Database publications:", len(df))

    pending = []

    for _, row in df.iterrows():

        key = (
            str(row["PMID"]),
            MODEL,
            PROMPT_VERSION,
            article_hash(row),
        )

        if key not in history:
            pending.append(row)

    print("Pending publications:", len(pending))

    if not args.export_only:

        if not args.all:
            pending = pending[:args.limit]

        print("Screening this run:", len(pending))

        for index, row in enumerate(pending, 1):

            pmid = str(row["PMID"])

            print(
                f"\n[{index}/{len(pending)}] "
                f"Screening PMID {pmid}"
            )

            try:

                result = screen_article(row)

                record = {
                    "PMID": pmid,
                    "model": MODEL,
                    "prompt_version": PROMPT_VERSION,
                    "source_hash": article_hash(row),
                    "screened_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    **result,
                }

                save_result(record)

                key = (
                    pmid,
                    MODEL,
                    PROMPT_VERSION,
                    record["source_hash"],
                )

                history[key] = record

                print(
                    result["decision"],
                    "|",
                    result["relevance"],
                    "|",
                    result["study_design"],
                )

                time.sleep(0.3)

            except Exception as error:

                print(
                    f"Error screening PMID {pmid}: "
                    f"{error}"
                )

                print(
                    "Stopping. Completed results are saved."
                )

                break

    export_results(df, history)


if __name__ == "__main__":
    main()