import os
import json
import time
import argparse
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
INPUT_FILE = Path("filter_validation_sample.csv")
OUTPUT_FILE = Path("ai_screening_results.csv")

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    timeout=60.0,
    max_retries=2,
)

SYSTEM_PROMPT = """
You are screening PubMed publications for CardioEvidence,
a clinical cardiovascular research discovery platform.

Use ONLY the provided title, abstract, and PubMed metadata.
Do not invent missing information.

Evaluate two independent dimensions:

1. Cardiovascular relevance:
- Core Cardiovascular: The main research question directly concerns
  cardiovascular disease, cardiovascular interventions, or outcomes.
- Cardiovascular Related: Cardiovascular outcomes are a meaningful
  secondary focus, or the research is relevant to cardiovascular prevention.
- Borderline: Cardiovascular relevance is indirect or uncertain.
- Not Relevant: The research does not meaningfully concern cardiovascular medicine.

2. Actual publication design:
- Randomized Controlled Trial
- Observational Study
- Guideline or Statement
- Systematic Review or Meta-analysis
- Narrative Review
- Case Report
- Protocol
- Editorial or Correction
- Other or Uncertain

Important:
- A review DISCUSSING randomized trials is not itself an RCT.
- A protocol for an RCT is not a completed RCT.
- A paper citing cohort studies is not necessarily observational research.
- Use the study's actual methods and objectives.
- If information is insufficient, choose Other or Uncertain.

Return a decision:
- Approve: clearly relevant, with an eligible publication design.
- Review: uncertainty about relevance or publication design.
- Exclude: clearly irrelevant or clearly ineligible publication design.

Eligible designs:
Randomized Controlled Trial, Observational Study, Guideline or Statement.

Be conservative about exclusion. When unsure, choose Review.

Clinical priority is an integer from 1 to 5.
It is for ranking only, never for exclusion.

Provide a short reason grounded in the article.
"""
CARDIOLOGY_SCOPE_RULES = """
ADDITIONAL CARDIOEVIDENCE SCREENING RULES

CardioEvidence is a clinical cardiovascular research platform,
not a general biomedical research database.

Evaluate the PRIMARY research question, population,
intervention, and outcomes.

APPROVE studies primarily investigating:

1. Coronary artery disease, ACS, PCI, CABG, and coronary imaging.
2. Heart failure, cardiomyopathies, and mechanical circulatory support.
3. Cardiac electrophysiology, arrhythmias, ablation, and devices.
4. Valvular and structural heart disease, including TAVR and TEER.
5. Cardiovascular prevention, hypertension, lipids, and atherosclerosis.
6. Pulmonary embolism, pulmonary hypertension, and venous thrombosis.
7. Peripheral arterial disease, aortic disease, and vascular interventions.
8. Cardiac surgery and congenital heart disease.
9. Cardiometabolic therapies when cardiovascular disease,
   cardiovascular risk reduction, or cardiovascular outcomes
   are central to the study.

DO NOT APPROVE solely because an article:

- Mentions cardiovascular disease as a comorbidity.
- Uses a cardiovascular medication for a noncardiac indication.
- Reports blood pressure or heart rate as incidental measurements.
- Includes cardiovascular risk factors without studying
  cardiovascular disease or prevention.
- Studies a primarily neurological, ophthalmological,
  oncological, infectious, or renal outcome.

Examples:

A trial of an SGLT2 inhibitor evaluating heart failure
hospitalization is cardiovascular research.

A trial of an SGLT2 inhibitor evaluating kidney outcomes
without cardiovascular endpoints is primarily nephrology.

A study of mechanical thrombectomy for ischemic stroke
is primarily neurology.

A study of pulmonary embolism catheter-directed therapy
is cardiovascular/vascular research.

A study of RSV hospitalization mentioning heart failure
as a comorbidity is not automatically cardiovascular research.

When the primary specialty is uncertain, choose Review.

Never exclude a clearly relevant original cardiovascular
study because it is small, negative, or has limited
clinical impact.

Study importance determines ranking, not eligibility.

For publication design, distinguish original research
from reviews, meta-analyses, protocols, and editorials.

If an article reports original patient-level outcomes
from a registry or retrospective cohort, classify it
as an observational study.

Do not infer that a study is randomized simply because
it discusses randomized trials.

When uncertain about eligibility, choose Review.
"""

SYSTEM_PROMPT += CARDIOLOGY_SCOPE_RULES

SCREENING_SCHEMA = {
    "type": "object",
    "properties": {
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
        "decision": {
            "type": "string",
            "enum": ["Approve", "Review", "Exclude"],
        },
        "subspecialty": {
            "type": "string",
        },
        "clinical_priority": {
            "type": "integer",
        },
        "reason": {
            "type": "string",
        },
    },
    "required": [
        "relevance",
        "study_design",
        "decision",
        "subspecialty",
        "clinical_priority",
        "reason",
    ],
    "additionalProperties": False,
}


def screen_article(row):
    article = {
        "pmid": row.get("PMID", ""),
        "title": row.get("Title", ""),
        "abstract": row.get("Abstract", ""),
        "publication_types": row.get("Publication Types", ""),
        "journal": row.get("Journal", ""),
    }

    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=json.dumps(article, ensure_ascii=False),
        text={
            "format": {
                "type": "json_schema",
                "name": "cardioevidence_screening",
                "strict": True,
                "schema": SCREENING_SCHEMA,
            }
        },
        max_output_tokens=600,
    )

    if response.status != "completed" or not response.output_text:
        raise RuntimeError(
            f"Incomplete model response: {response.status}"
        )

    result = json.loads(response.output_text)

    if not 1 <= result["clinical_priority"] <= 5:
        raise ValueError("Clinical priority must be between 1 and 5.")

    eligible_designs = {
        "Randomized Controlled Trial",
        "Observational Study",
        "Guideline or Statement",
    }

    eligible_relevance = {
        "Core Cardiovascular",
        "Cardiovascular Related",
    }

    # Safety rule: model cannot approve an ineligible article.
    if result["decision"] == "Approve":
        if (
            result["study_design"] not in eligible_designs
            or result["relevance"] not in eligible_relevance
        ):
            result["decision"] = "Review"
            result["reason"] += " [Approval requires manual review.]"

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    if not INPUT_FILE.exists():
        raise FileNotFoundError(INPUT_FILE)

    df = pd.read_csv(INPUT_FILE, dtype=str).fillna("")

    existing = pd.DataFrame()
    if OUTPUT_FILE.exists():
        existing = pd.read_csv(
            OUTPUT_FILE, dtype=str
        ).fillna("")

    completed = (
        set(existing["PMID"])
        if "PMID" in existing.columns
        else set()
    )

    pending = df[
        ~df["PMID"].isin(completed)
    ].head(args.limit)

    print(f"Model: {MODEL}")
    print(f"Articles to screen: {len(pending)}")

    for _, row in pending.iterrows():
        pmid = str(row["PMID"])

        print(f"\nScreening PMID {pmid}...")

        try:
            result = screen_article(row)

            record = {
                "PMID": pmid,
                "Title": row.get("Title", ""),
                "Original Relevance": row.get("Relevance", ""),
                "Original Study Design": row.get("Study Design", ""),
                "AI Model": MODEL,
                **result,
            }

            existing = pd.concat(
                [existing, pd.DataFrame([record])],
                ignore_index=True,
            )

            # Save after every successful screening.
            existing.to_csv(OUTPUT_FILE, index=False)
            completed.add(pmid)

            print(
                result["decision"],
                "|",
                result["relevance"],
                "|",
                result["study_design"],
            )

        except Exception as exc:
            print(f"Error screening PMID {pmid}: {exc}")
            print("Stopping to avoid repeated API charges.")
            break

        time.sleep(0.3)

    print("\nScreening complete.")
    print(f"Results saved to: {OUTPUT_FILE}")

    if not existing.empty and "decision" in existing.columns:
        print("\nDecisions:")
        print(existing["decision"].value_counts())


if __name__ == "__main__":
    main()