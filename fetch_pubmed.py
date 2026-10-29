import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ============================================================
# 1. REQUEST SESSION WITH AUTOMATIC RETRIES
# ============================================================

session = requests.Session()

retry_strategy = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
    respect_retry_after_header=True
)

adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


# ============================================================
# 2. CARDIOLOGY SEARCH QUERY
# ============================================================

CARDIOLOGY = """
(
    "Cardiovascular Diseases"[MeSH Terms]
    OR "Heart Diseases"[MeSH Terms]
    OR "Coronary Disease"[MeSH Terms]
    OR "Heart Failure"[MeSH Terms]
    OR "Arrhythmias, Cardiac"[MeSH Terms]
    OR "Heart Valve Diseases"[MeSH Terms]
    OR "Cardiomyopathies"[MeSH Terms]
    OR "Hypertension"[MeSH Terms]
    OR "Peripheral Arterial Disease"[MeSH Terms]
    OR "Atherosclerosis"[MeSH Terms]

    OR cardiovascular[Title/Abstract]
    OR cardiology[Title/Abstract]
    OR coronary[Title/Abstract]
    OR myocardial[Title/Abstract]
    OR cardiomyopathy[Title/Abstract]
    OR atherosclerosis[Title/Abstract]

    OR "heart failure"[Title/Abstract]
    OR "acute coronary syndrome"[Title/Abstract]
    OR "myocardial infarction"[Title/Abstract]
    OR "stable angina"[Title/Abstract]
    OR "coronary artery disease"[Title/Abstract]
    OR "ischemic heart disease"[Title/Abstract]

    OR "atrial fibrillation"[Title/Abstract]
    OR "atrial flutter"[Title/Abstract]
    OR "ventricular tachycardia"[Title/Abstract]
    OR "ventricular fibrillation"[Title/Abstract]
    OR "cardiac arrhythmia"[Title/Abstract]
    OR "catheter ablation"[Title/Abstract]
    OR pacemaker[Title/Abstract]
    OR "implantable cardioverter defibrillator"[Title/Abstract]
    OR "cardiac resynchronization"[Title/Abstract]

    OR "aortic stenosis"[Title/Abstract]
    OR "aortic regurgitation"[Title/Abstract]
    OR "mitral regurgitation"[Title/Abstract]
    OR "mitral stenosis"[Title/Abstract]
    OR "tricuspid regurgitation"[Title/Abstract]
    OR "valvular heart disease"[Title/Abstract]
    OR "transcatheter aortic valve"[Title/Abstract]
    OR "transcatheter mitral"[Title/Abstract]
    OR "transcatheter tricuspid"[Title/Abstract]
    OR TAVR[Title/Abstract]
    OR TAVI[Title/Abstract]
    OR TTVR[Title/Abstract]
    OR TEER[Title/Abstract]

    OR "percutaneous coronary intervention"[Title/Abstract]
    OR "coronary artery bypass"[Title/Abstract]
    OR "coronary stent"[Title/Abstract]
    OR "coronary angiography"[Title/Abstract]
    OR "fractional flow reserve"[Title/Abstract]
    OR "intravascular ultrasound"[Title/Abstract]

    OR "cardiogenic shock"[Title/Abstract]
    OR "cardiac arrest"[Title/Abstract]
    OR "mechanical circulatory support"[Title/Abstract]
    OR "left ventricular assist device"[Title/Abstract]

    OR "cardiac amyloidosis"[Title/Abstract]
    OR "hypertrophic cardiomyopathy"[Title/Abstract]
    OR "dilated cardiomyopathy"[Title/Abstract]
    OR "myocarditis"[Title/Abstract]
    OR "pericarditis"[Title/Abstract]

    OR "pulmonary arterial hypertension"[Title/Abstract]
    OR "pulmonary hypertension"[Title/Abstract]
    OR "peripheral artery disease"[Title/Abstract]
    OR "peripheral arterial disease"[Title/Abstract]
    OR "aortic aneurysm"[Title/Abstract]
    OR "aortic dissection"[Title/Abstract]

    OR "cardiovascular outcomes"[Title/Abstract]
    OR "major adverse cardiovascular events"[Title/Abstract]
    OR "cardiovascular mortality"[Title/Abstract]
    OR "cardiovascular prevention"[Title/Abstract]
    OR "lipid lowering"[Title/Abstract]
    OR "LDL cholesterol"[Title/Abstract]
    OR "familial hypercholesterolemia"[Title/Abstract]
    OR "resistant hypertension"[Title/Abstract]
    OR "blood pressure lowering"[Title/Abstract]

    OR "echocardiography"[Title/Abstract]
    OR "cardiac magnetic resonance"[Title/Abstract]
    OR "cardiac MRI"[Title/Abstract]
    OR "cardiac computed tomography"[Title/Abstract]
    OR "coronary CT"[Title/Abstract]
    OR "coronary calcium"[Title/Abstract]
)
"""


# ============================================================
# 3. STUDY CATEGORIES
# ============================================================

CATEGORIES = {

    "Randomized Controlled Trials": """
    (
        "Randomized Controlled Trial"[Publication Type]
        OR (
            randomized[Title/Abstract]
            OR randomised[Title/Abstract]
            OR randomly[Title/Abstract]
        )
    )
    NOT (
        "Randomized Controlled Trial Protocol"[Title]
        OR "study protocol"[Title]
    )
    """,

    "Observational Studies": """
    (
        "Observational Study"[Publication Type]
        OR "Cohort Studies"[MeSH Terms]
        OR "Case-Control Studies"[MeSH Terms]
        OR cohort[Title/Abstract]
        OR registry[Title/Abstract]
        OR retrospective[Title/Abstract]
        OR prospective[Title/Abstract]
        OR "case-control"[Title/Abstract]
    )
    """,

    "Guidelines & Statements": """
    (
        "Practice Guideline"[Publication Type]
        OR "Guideline"[Publication Type]
        OR guideline[Title]
        OR "scientific statement"[Title]
        OR "expert consensus"[Title]
        OR "consensus statement"[Title]
        OR "position statement"[Title]
    )
    """
}


# ============================================================
# 4. DATABASE FILE
# ============================================================

DATA_FILE = Path("publications.csv")


# ============================================================
# 5. SEARCH PUBMED
# ============================================================

def search_pubmed(query, days=14):
    """Retrieve all matching PMIDs using pagination."""

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    all_ids = []
    batch_size = 500

    params = {
        "db": "pubmed",
        "term": query,
        "datetype": "edat",
        "mindate": start_date.isoformat(),
        "maxdate": end_date.isoformat(),
        "retmode": "json",
        "retmax": 0,
        "tool": "CardioEvidence"
    }

    # First, find total number of matching articles
    response = session.post(
        f"{BASE_URL}/esearch.fcgi",
        data=params,
        timeout=30
    )

    response.raise_for_status()

    total = int(
        response.json()["esearchresult"]["count"]
    )

    print(
        f"Total matching publications: {total}",
        flush=True
    )

    # Retrieve PMIDs in batches
    for start in range(0, total, batch_size):

        params["retstart"] = start
        params["retmax"] = batch_size

        response = session.post(
            f"{BASE_URL}/esearch.fcgi",
            data=params,
            timeout=30
        )

        response.raise_for_status()

        batch_ids = response.json()[
            "esearchresult"
        ]["idlist"]

        all_ids.extend(batch_ids)

        print(
            f"Retrieved {len(all_ids)} of {total} PMIDs",
            flush=True
        )

        time.sleep(0.4)

    return list(dict.fromkeys(all_ids))


# ============================================================
# 6. XML TEXT EXTRACTION
# ============================================================

def get_text(element):
    """Extract text from an XML element."""

    if element is None:
        return ""

    return "".join(element.itertext()).strip()


# ============================================================
# 7. EXTRACT PUBLICATION DATES
# ============================================================

def extract_pubmed_dates(article):
    """Extract publication and PubMed entry dates."""

    publication_date = ""
    pubmed_entry_date = ""

    # Electronic publication date
    electronic_date = article.find(
        ".//Article/ArticleDate[@DateType='Electronic']"
    )

    if electronic_date is not None:

        year = get_text(electronic_date.find("Year"))
        month = get_text(electronic_date.find("Month"))
        day = get_text(electronic_date.find("Day"))

        if year and month and day:
            publication_date = f"{year}-{month}-{day}"

    # Publication history date
    if not publication_date:

        for history in article.findall(
            ".//PubmedData/History/PubMedPubDate"
        ):

            if history.get("PubStatus") in [
                "epublish",
                "aheadofprint"
            ]:

                year = get_text(history.find("Year"))
                month = get_text(history.find("Month"))
                day = get_text(history.find("Day"))

                if year and month and day:

                    publication_date = (
                        f"{year}-{month}-{day}"
                    )

                    break

    # PubMed entry date
    for history in article.findall(
        ".//PubmedData/History/PubMedPubDate"
    ):

        if history.get("PubStatus") in [
            "entrez",
            "pubmed"
        ]:

            year = get_text(history.find("Year"))
            month = get_text(history.find("Month"))
            day = get_text(history.find("Day"))

            if year and month and day:

                pubmed_entry_date = (
                    f"{year}-{month}-{day}"
                )

                break

    return publication_date, pubmed_entry_date


# ============================================================
# 8. FETCH ARTICLE DETAILS
# ============================================================

def fetch_details(pmids):
    """Download PubMed article metadata."""

    articles = []

    for i in range(0, len(pmids), 100):

        batch = pmids[i:i + 100]

        response = session.post(
            f"{BASE_URL}/efetch.fcgi",
            data={
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
                "tool": "CardioEvidence"
            },
            timeout=60
        )

        response.raise_for_status()

        root = ET.fromstring(response.content)

        for article in root.findall("./PubmedArticle"):

            pmid = get_text(
                article.find(".//MedlineCitation/PMID")
            )

            title = get_text(
                article.find(".//Article/ArticleTitle")
            )

            journal = get_text(
                article.find(".//Journal/Title")
            )

            # Extract abstract
            abstract_parts = []

            for part in article.findall(
                ".//Article/Abstract/AbstractText"
            ):

                label = part.get("Label", "")
                content = get_text(part)

                if label:
                    content = f"{label}: {content}"

                abstract_parts.append(content)

            abstract = "\n".join(abstract_parts)

            # Extract publication types
            publication_types = [
                get_text(item)
                for item in article.findall(
                    ".//PublicationTypeList/PublicationType"
                )
            ]

            # Extract year
            pub_date = article.find(
                ".//Article/Journal/JournalIssue/PubDate"
            )

            year = ""

            if pub_date is not None:

                year = get_text(pub_date.find("Year"))

                if not year:

                    medline_date = get_text(
                        pub_date.find("MedlineDate")
                    )

                    year = medline_date[:4]

            publication_date, pubmed_entry_date = (
                extract_pubmed_dates(article)
            )

            articles.append({
                "PMID": pmid,
                "Title": title,
                "Journal": journal,
                "Year": year,
                "Publication Date": publication_date,
                "PubMed Entry Date": pubmed_entry_date,
                "Abstract": abstract,
                "Publication Types": "; ".join(
                    publication_types
                ),
                "PubMed URL":
                    f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "Date Retrieved":
                    datetime.now(
                        timezone.utc
                    ).date().isoformat()
            })

        print(
            f"Processed {min(i + 100, len(pmids))} "
            f"of {len(pmids)} publications",
            flush=True
        )

        time.sleep(0.4)

    return articles


# ============================================================
# 9. MAIN FUNCTION
# ============================================================

def main():

    all_articles = {}

    # Step 1: Retrieve new publications
    for category, filter_query in CATEGORIES.items():

        print(
            f"Searching: {category}",
            flush=True
        )

        query = f"({CARDIOLOGY}) AND ({filter_query})"

        pmids = search_pubmed(query)

        print(
            f"Found {len(pmids)} PMIDs",
            flush=True
        )

        articles = fetch_details(pmids)

        for article in articles:

            pmid = article["PMID"]

            if pmid not in all_articles:

                article["Category"] = category
                all_articles[pmid] = article

            else:

                existing = all_articles[pmid]["Category"]

                if category not in existing.split("; "):

                    all_articles[pmid]["Category"] += (
                        "; " + category
                    )

    # Step 2: Load existing publications ONCE
    if DATA_FILE.exists():

        print(
            "Loading existing publications...",
            flush=True
        )

        old_df = pd.read_csv(
            DATA_FILE,
            dtype=str
        ).fillna("")

        for _, row in old_df.iterrows():

            pmid = row["PMID"]
            old_article = row.to_dict()

            if pmid not in all_articles:

                all_articles[pmid] = old_article

            else:

                # Fill missing fields
                for key, value in old_article.items():

                    if (
                        key not in all_articles[pmid]
                        or not all_articles[pmid][key]
                    ):

                        all_articles[pmid][key] = value

    # Step 3: Save publications
    if not all_articles:

        print("No publications found.")
        return

    df = pd.DataFrame(
        all_articles.values()
    )

    df = df.drop_duplicates(
        subset=["PMID"]
    )

    df = df.sort_values(
        by="PMID",
        ascending=False,
        key=lambda s: pd.to_numeric(
            s,
            errors="coerce"
        )
    )

    df.to_csv(
        DATA_FILE,
        index=False
    )

    print(
        f"Saved {len(df)} publications",
        flush=True
    )


if __name__ == "__main__":
    main()