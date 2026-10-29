import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    print("\n========== STEP 1: GPT-6 LUNA ==========", flush=True)

    subprocess.run([
        sys.executable,
        "ai_screen.py",
        "--input",
        "publications.csv",
        "--limit",
        str(args.limit)
    ], check=True)

    print("\n========== STEP 2: GPT-6.1 SOL ==========", flush=True)

    review_file = Path("ai_review_queue.csv")

    if review_file.exists():
        review_df = pd.read_csv(review_file, dtype=str).fillna("")

        if not review_df.empty:
            subprocess.run([
                sys.executable,
                "sol_review.py",
                "--limit",
                str(len(review_df))
            ], check=True)

            sol_file = Path("sol_review_results.csv")

            if sol_file.exists():
                sol_df = pd.read_csv(sol_file, dtype=str).fillna("")

                combined = review_df.merge(
                    sol_df,
                    on="PMID",
                    how="left",
                    suffixes=("", "_sol"),
                    validate="one_to_one"
                )

                combined.to_csv("combined_ai_review.csv", index=False)
                print("\nSaved: combined_ai_review.csv")

    print("\nPipeline completed!")


if __name__ == "__main__":
    main()
