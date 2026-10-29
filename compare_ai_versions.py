import pandas as pd

# Load both AI screening versions
v1 = pd.read_csv("ai_screening_results_v1.csv", dtype=str)
v2 = pd.read_csv("ai_screening_results.csv", dtype=str)

# Match publications using PMID
comparison = v1.merge(
    v2,
    on="PMID",
    suffixes=("_v1", "_v2"),
    validate="one_to_one"
)

print("\n=== ORIGINAL AI DECISIONS ===")
print(v1["decision"].value_counts())

print("\n=== UPDATED AI DECISIONS ===")
print(v2["decision"].value_counts())

# Identify changed decisions
changes = comparison[
    comparison["decision_v1"] != comparison["decision_v2"]
]

print("\n=== CHANGED DECISIONS ===")
print(f"{len(changes)} out of {len(comparison)} articles")

print("\n=== DECISION TRANSITIONS ===")
print(
    pd.crosstab(
        comparison["decision_v1"],
        comparison["decision_v2"]
    )
)

# Save comparison
comparison.to_csv(
    "ai_comparison.csv",
    index=False
)

print("\nSaved: ai_comparison.csv")