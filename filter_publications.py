import pandas as pd
import re
from pathlib import Path


# ============================================================
# 1. FILES
# ============================================================

INPUT_FILE = Path("publications.csv")
OUTPUT_FILE = Path("filtered_publications.csv")
REVIEW_FILE = Path("publications_review.csv")


# ============================================================
# 2. CORE CARDIOVASCULAR TERMS
# ============================================================

CORE_TERMS = [
    # General cardiovascular
    "cardiovascular",
    "cardiology",
    "cardiac",
    "coronary",
    "myocardial",
    "heart failure",
    "cardiomyopathy",
    "atherosclerosis",

    # Coronary disease
    "myocardial infarction",
    "acute coronary syndrome",
    "coronary artery disease",
    "percutaneous coronary intervention",
    "coronary bypass",
    "coronary revascularization",
    "coronary stent",
    "fractional flow reserve",

    # Electrophysiology
    "atrial fibrillation",
    "atrial flutter",
    "ventricular tachycardia",
    "ventricular fibrillation",
    "cardiac arrhythmia",
    "catheter ablation",
    "pacemaker",
    "defibrillator",
    "cardiac resynchronization",

    # Structural heart
    "aortic stenosis",
    "aortic regurgitation",
    "mitral regurgitation",
    "mitral stenosis",
    "tricuspid regurgitation",
    "valvular heart disease",
    "transcatheter valve",
    "tavr",
    "tavi",
    "ttvr",
    "teer",

    # Heart failure and shock
    "cardiogenic shock",
    "mechanical circulatory support",
    "ventricular assist device",
    "cardiac amyloidosis",
    "myocarditis",

    # Vascular medicine
    "peripheral artery disease",
    "peripheral arterial disease",
    "aortic aneurysm",
    "aortic dissection",
    "endovascular aneurysm",
    "vascular intervention",

    # Cardiovascular prevention
    "hypertension",
    "dyslipidemia",
    "lipid lowering",
    "ldl cholesterol",
    "cardiovascular prevention",
    "cardiovascular mortality",
    "major adverse cardiovascular events",

    # Antithrombotic therapy
    "anticoagulation",
    "antiplatelet",
    "venous thromboembolism",
    "deep vein thrombosis",
    "pulmonary embolism",
]


# ============================================================
# 3. BROADER CARDIOVASCULAR TERMS
# ============================================================

BORDERLINE_TERMS = [
    "blood pressure",
    "cholesterol",
    "vascular",
    "endothelial",
    "hemodynamic",
    "thrombosis",
    "thromboembolism",
    "metabolic syndrome",
    "cardiometabolic",
    "exercise capacity",
    "cardiorespiratory",
    "arterial stiffness",
    "pulse wave velocity",
    "heart rate variability",
    "echocardiography",
]


# ============================================================
# 4. PUBLICATION TYPES TO EXCLUDE
# ============================================================

EXCLUDED_TYPES = [
    "case reports",
    "published erratum",
    "retracted publication",
    "retraction of publication",
    "editorial",
    "letter",
    "comment",
    "news",
]

EXCLUDED_TITLE_TERMS = [
    "study protocol",
    "trial protocol",
    "protocol for a",
    "correction:",
    "erratum:",
    "retraction:",
]


# ============================================================
# 5. KEYWORD MATCHING
# ============================================================

def contains_term(text, terms):
    """Check whether text contains any listed term."""

    text = str(text).lower()

    for term in terms:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"

        if re.search(pattern, text):
            return True

    return False


# ============================================================
# 6. CARDIOVASCULAR RELEVANCE
# ============================================================

def classify_relevance(row):
    """
    Classify cardiovascular relevance using title and abstract.

    This is a preliminary rule-based classifier.
    """

    title = str(row.get("Title", "")).lower()
    abstract = str(row.get("Abstract", "")).lower()

    title_core = contains_term(title, CORE_TERMS)
    abstract_core = contains_term(abstract, CORE_TERMS)

    title_borderline = contains_term(
        title,
        BORDERLINE_TERMS
    )

    abstract_borderline = contains_term(
        abstract,
        BORDERLINE_TERMS
    )

    if title_core:
        return "Core Cardiovascular"

    if abstract_core:
        return "Borderline"

    if title_borderline or abstract_borderline:
        return "Borderline"

    return "Not Relevant"


# ============================================================
# 7. PUBLICATION ELIGIBILITY
# ============================================================

def classify_eligibility(row):

    title = str(row.get("Title", "")).lower()

    publication_types = str(
        row.get("Publication Types", "")
    ).lower()

    if contains_term(publication_types, EXCLUDED_TYPES):
        return "Exclude"

    if contains_term(title, EXCLUDED_TITLE_TERMS):
        return "Exclude"

    return "Eligible"


# ============================================================
# 8. STUDY DESIGN
# ============================================================

def classify_study_design(row):

    title = str(row.get("Title", "")).lower()
    abstract = str(row.get("Abstract", "")).lower()

    publication_types = str(
        row.get("Publication Types", "")
    ).lower()

    category = str(row.get("Category", "")).lower()

    # Guidelines and statements
    guideline_terms = [
        "guideline",
        "scientific statement",
        "expert consensus",
        "consensus statement",
        "position statement",
    ]

    if (
        contains_term(title, guideline_terms)
        or "practice guideline" in publication_types
        or "guideline" in publication_types
    ):
        return "Guidelines & Statements"

    # Randomized trials
    if (
        "randomized controlled trial" in publication_types
        or "randomised controlled trial" in publication_types
        or (
            contains_term(
                title + " " + abstract,
                ["randomized", "randomised"]
            )
            and "randomized controlled trials" in category
        )
    ):
        return "Randomized Controlled Trials"

    # Observational studies
    observational_terms = [
        "cohort",
        "registry",
        "retrospective",
        "prospective",
        "case-control",
        "observational",
    ]

    if (
        "observational study" in publication_types
        or contains_term(
            title + " " + abstract,
            observational_terms
        )
    ):
        return "Observational Studies"

    return "Uncertain"


# ============================================================
# 9. MAIN FUNCTION
# ============================================================

def main():

    if not INPUT_FILE.exists():
        print("Error: publications.csv not found.")
        return

    print("Loading CardioEvidence database...")

    df = pd.read_csv(
        INPUT_FILE,
        dtype=str
    ).fillna("")

    print(f"Total publications: {len(df)}")

    # Classify cardiovascular relevance
    df["Relevance"] = df.apply(
        classify_relevance,
        axis=1
    )

    # Classify eligibility
    df["Eligibility"] = df.apply(
        classify_eligibility,
        axis=1
    )

    # Classify study design
    df["Study Design"] = df.apply(
        classify_study_design,
        axis=1
    )

    # Identify publications ready for display
    eligible = df[
        (df["Relevance"] == "Core Cardiovascular")
        & (df["Eligibility"] == "Eligible")
        & (df["Study Design"] != "Uncertain")
    ].copy()

    # Identify publications needing review
    review = df[
        (df["Relevance"] == "Borderline")
        | (df["Study Design"] == "Uncertain")
    ].copy()

    # Save results
    eligible.to_csv(
        OUTPUT_FILE,
        index=False
    )

    review.to_csv(
        REVIEW_FILE,
        index=False
    )

    print("\n========== FILTERING RESULTS ==========")

    print("\nCardiovascular relevance:")
    print(df["Relevance"].value_counts())

    print("\nPublication eligibility:")
    print(df["Eligibility"].value_counts())

    print("\nStudy design:")
    print(df["Study Design"].value_counts())

    print("\n=======================================")

    print(f"Eligible publications: {len(eligible)}")
    print(f"Publications needing review: {len(review)}")

    print("\nFiles saved:")
    print("filtered_publications.csv")
    print("publications_review.csv")


if __name__ == "__main__":
    main()