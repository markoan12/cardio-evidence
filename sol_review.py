import os
import json
import time
import argparse
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = "gpt-6.1-sol"

INPUT_FILE = Path("ai_review_queue.csv")
OUTPUT_FILE = Path("sol_review_results.csv")

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    timeout=120.0,
    max_retries=2,
)

SYSTEM_PROMPT = """
You are a senior clinical cardiology evidence reviewer for CardioEvidence.

CardioEvidence is a clinical cardiovascular research discovery platform.

Evaluate the article's PRIMARY research question, population,
intervention, and outcomes.

Relevant areas include:
- Coronary disease, ACS, PCI, and CABG
- Heart failure, cardiomyopathy, and mechanical circulatory support
- Arrhythmias, electrophysiology, and cardiac devices
- Valvular and structural heart disease
- Hypertension, lipids, and cardiovascular prevention
- Pulmonary embolism, pulmonary hypertension, and VTE
- Peripheral arterial disease, aortic disease, and vascular medicine
- Cardiac surgery and congenital cardiovascular disease
- Cardiometabolic therapies when cardiovascular outcomes are central

Do not consider an article relevant merely because it mentions:
- A cardiovascular comorbidity
- A cardiovascular medication used for a noncardiac indication
- Incidental blood pressure or heart rate measurements
- Cardiovascular risk factors without cardiovascular outcomes

Assess study design independently.

Eligible study designs:
- Original randomized controlled trials
- Original observational studies
- Clinical guidelines and scientific statements

Generally exclude:
- Narrative reviews
- Systematic reviews and meta-analyses
- Study protocols without results
- Editorials and corrections
- Case reports

For every article, return:
1. A decision: Approve, Review, or Exclude
2. Cardiovascular relevance
3. Study design
4. Clinical priority from 1 to 5
5. A concise explanation

Use Review when the evidence is insufficient or the scope is ambiguous.

Do not automatically agree with the previous AI model.
Do not invent article findings.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["Approve", "Review", "Exclude"],
        },
        "relevance": {
            "type": "string",
            "enum": [
                "Core Cardiovascular",
                "Cardiovascular Related",
                "Borderline",
                "Not Relevant",
            ],
        },
        "study_design": {
            "type": "string",
            "enum": [
                "Randomized Controlled Trial",
                "Observational Study",
                "Guideline or Statement",
                "Systematic Review or Meta-analysis",
                "Narrative Review",
                "Case Report",
                "Protocol",
                "Editorial or Correction",
                "Other or Uncertain",
            ],
        },
        "clinical_priority": {
            "type": "integer",
        },
        "reason": {
            "type": "string",
        },
    },
    "required": [
        "decision",
        "relevance",
        "study_design",
        "clinical_priority",
        "reason",
    ],
    "additionalProperties": False,
}


def review_article(row):

    article = {
        "PMID": str(row["PMID"]),
        "Title": row.get("Title", ""),
        "Abstract": row.get("Abstract", ""),
        "Publication Types": row.get("Publication Types", ""),
        "Journal": row.get("Journal", ""),
    }

    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=json.dumps(article, ensure_ascii=False),
        text={
            "format": {
                "type": "json_schema",
                "name": "sol_cardiology_review",
                "strict": True,
                "schema": SCHEMA,
            }
        },
        max_output_tokens=1200,
    )

    if response.status != "completed" or not response.output_text:
        raise RuntimeError(
            f"Incomplete response: {response.status}"
        )

    result = json.loads(response.output_text)

    if not 1 <= result["clinical_priority"] <= 5:
        raise ValueError("Invalid clinical priority")

    eligible_designs = {
        "Randomized Controlled Trial",
        "Observational Study",
        "Guideline or Statement",
    }

    eligible_relevance = {
        "Core Cardiovascular",
        "Cardiovascular Related",
    }

    if result["decision"] == "Approve":
        if (
            result["study_design"] not in eligible_designs
            or result["relevance"] not in eligible_relevance
        ):
            result["decision"] = "Review"
            result["reason"] += " [Manual eligibility check required.]"

    return result


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=250)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    df = pd.read_csv(INPUT_FILE, dtype=str).fillna("")

    if df["PMID"].duplicated().any():
        raise ValueError("Duplicate PMIDs in review queue")

    if OUTPUT_FILE.exists():
        existing = pd.read_csv(OUTPUT_FILE, dtype=str).fillna("")
    else:
        existing = pd.DataFrame()

    completed = (
        set(existing["PMID"])
        if "PMID" in existing.columns
        else set()
    )

    pending = df[
        ~df["PMID"].isin(completed)
    ].head(args.limit)

    print(f"\nSol second review: {len(pending)} articles")
    print(f"Previously completed: {len(completed)}")

    for index, row in pending.iterrows():

        pmid = str(row["PMID"])

        try:
            result = review_article(row)

            record = {
                "PMID": pmid,
                "Title": row.get("Title", ""),
                "Luna Decision": row.get("AI Decision", ""),
                "Luna Reason": row.get("reason", ""),
                "Sol Model": MODEL,
                "Sol Decision": result["decision"],
                "Sol Relevance": result["relevance"],
                "Sol Study Design": result["study_design"],
                "Sol Priority": result["clinical_priority"],
                "Sol Reason": result["reason"],
            }

            existing = pd.concat(
                [existing, pd.DataFrame([record])],
                ignore_index=True,
            )

            existing.to_csv(OUTPUT_FILE, index=False)
            completed.add(pmid)

            print(
                pmid,
                "| Luna:", record["Luna Decision"],
                "| Sol:", record["Sol Decision"],
            )

            time.sleep(0.3)

        except Exception as error:
            print(f"Error reviewing PMID {pmid}: {error}")
            print("Stopping. Completed results remain saved.")
            break

    print("\n========== SOL REVIEW RESULTS ==========")

    if not existing.empty:
        print(existing["Sol Decision"].value_counts())

    print("========================================")
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()