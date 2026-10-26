import requests
import pandas as pd
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

CARDIOLOGY = """
(
 cardiovascular[Title/Abstract]
 OR cardiac[Title/Abstract]
 OR cardiology[Title/Abstract]
 OR coronary[Title/Abstract]
 OR heart failure[Title/Abstract]
 OR arrhythmia[Title/Abstract]
 OR valvular[Title/Abstract]
 OR aortic valve[Title/Abstract]
 OR mitral valve[Title/Abstract]
 OR tricuspid valve[Title/Abstract]
 OR myocardial infarction[Title/Abstract]
)
"""

CATEGORIES = {
    "Randomized Controlled Trials": """
    (
      randomized controlled trial[Publication Type]
      OR randomized[Title/Abstract]
      OR randomised[Title/Abstract]
    )
    """,

    "Observational Studies": """
    (
      observational study[Publication Type]
      OR cohort[Title/Abstract]
      OR registry[Title/Abstract]
      OR retrospective[Title/Abstract]
      OR prospective[Title/Abstract]
      OR case-control[Title/Abstract]
    )
    """,

    "Guidelines & Statements": """
    (
      practice guideline[Publication Type]
      OR guideline[Title]
      OR scientific statement[Title]
      OR expert consensus[Title]
      OR consensus statement[Title]
    )
    """
}

DATA_FILE = Path("publications.csv")


def search_pubmed(query, days=14):
    """Find PMIDs added to PubMed recently."""

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    params = {
        "db": "pubmed",
        "term": query,
        "datetype": "edat",
        "mindate": start_date.isoformat(),
        "maxdate": end_date.isoformat(),
        "retmax": 1000,
        "retmode": "json",
        "tool": "CardioEvidence"
    }

    response = requests.get(
        f"{BASE_URL}/esearch.fcgi",
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()["esearchresult"]

    count = int(data["count"])
    ids = data["idlist"]

    if count > len(ids):
        print(
            f"Warning: {count} results found, "
            f"but only {len(ids)} retrieved."
        )

    return ids


def get_text(element):
    """Extract text from an XML element."""

    if element is None:
        return ""

    return "".join(element.itertext()).strip()


def fetch_details(pmids):
    """Download PubMed article metadata."""

    articles = []

    for i in range(0, len(pmids), 100):

        batch = pmids[i:i + 100]

        response = requests.post(
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

        for article in root.findall(".//PubmedArticle"):

            pmid = get_text(
                article.find(".//MedlineCitation/PMID")
            )

            title = get_text(
                article.find(".//Article/ArticleTitle")
            )

            journal = get_text(
                article.find(".//Journal/Title")
            )

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

            publication_types = [
                get_text(item)
                for item in article.findall(
                    ".//PublicationTypeList/PublicationType"
                )
            ]

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

            articles.append({
                "PMID": pmid,
                "Title": title,
                "Journal": journal,
                "Year": year,
                "Abstract": abstract,
                "Publication Types": "; ".join(publication_types),
                "PubMed URL":
                    f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "Date Retrieved":
                    datetime.now(timezone.utc).date().isoformat()
            })

        time.sleep(0.4)

    return articles


def main():

    all_articles = {}

    for category, filter_query in CATEGORIES.items():

        print(f"Searching: {category}")

        query = f"{CARDIOLOGY} AND {filter_query}"

        pmids = search_pubmed(query)

        print(f"Found {len(pmids)} PMIDs")

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

    if DATA_FILE.exists():
        old_df = pd.read_csv(
            DATA_FILE,
            dtype=str
        ).fillna("")

        for _, row in old_df.iterrows():

            pmid = row["PMID"]

            if pmid not in all_articles:
                all_articles[pmid] = row.to_dict()

    if not all_articles:
        print("No publications found.")
        return

    df = pd.DataFrame(all_articles.values())

    df = df.drop_duplicates(subset=["PMID"])

    df = df.sort_values(
        by="PMID",
        ascending=False,
        key=lambda s: pd.to_numeric(s, errors="coerce")
    )

    df.to_csv(DATA_FILE, index=False)

    print(f"Saved {len(df)} publications")


if __name__ == "__main__":
    main()
    import requests
import pandas as pd
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

CARDIOLOGY = """
(
 cardiovascular[Title/Abstract]
 OR cardiac[Title/Abstract]
 OR cardiology[Title/Abstract]
 OR coronary[Title/Abstract]
 OR heart failure[Title/Abstract]
 OR arrhythmia[Title/Abstract]
 OR valvular[Title/Abstract]
 OR aortic valve[Title/Abstract]
 OR mitral valve[Title/Abstract]
 OR tricuspid valve[Title/Abstract]
 OR myocardial infarction[Title/Abstract]
)
"""

CATEGORIES = {
    "Randomized Controlled Trials": """
    (
      randomized controlled trial[Publication Type]
      OR randomized[Title/Abstract]
      OR randomised[Title/Abstract]
    )
    """,

    "Observational Studies": """
    (
      observational study[Publication Type]
      OR cohort[Title/Abstract]
      OR registry[Title/Abstract]
      OR retrospective[Title/Abstract]
      OR prospective[Title/Abstract]
      OR case-control[Title/Abstract]
    )
    """,

    "Guidelines & Statements": """
    (
      practice guideline[Publication Type]
      OR guideline[Title]
      OR scientific statement[Title]
      OR expert consensus[Title]
      OR consensus statement[Title]
    )
    """
}

DATA_FILE = Path("publications.csv")


def search_pubmed(query, days=14):
    """Find PMIDs added to PubMed recently."""

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    params = {
        "db": "pubmed",
        "term": query,
        "datetype": "edat",
        "mindate": start_date.isoformat(),
        "maxdate": end_date.isoformat(),
        "retmax": 1000,
        "retmode": "json",
        "tool": "CardioEvidence"
    }

    response = requests.get(
        f"{BASE_URL}/esearch.fcgi",
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()["esearchresult"]

    count = int(data["count"])
    ids = data["idlist"]

    if count > len(ids):
        print(
            f"Warning: {count} results found, "
            f"but only {len(ids)} retrieved."
        )

    return ids


def get_text(element):
    """Extract text from an XML element."""

    if element is None:
        return ""

    return "".join(element.itertext()).strip()


def fetch_details(pmids):
    """Download PubMed article metadata."""

    articles = []

    for i in range(0, len(pmids), 100):

        batch = pmids[i:i + 100]

        response = requests.post(
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

        for article in root.findall(".//PubmedArticle"):

            pmid = get_text(
                article.find(".//MedlineCitation/PMID")
            )

            title = get_text(
                article.find(".//Article/ArticleTitle")
            )

            journal = get_text(
                article.find(".//Journal/Title")
            )

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

            publication_types = [
                get_text(item)
                for item in article.findall(
                    ".//PublicationTypeList/PublicationType"
                )
            ]

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

            articles.append({
                "PMID": pmid,
                "Title": title,
                "Journal": journal,
                "Year": year,
                "Abstract": abstract,
                "Publication Types": "; ".join(publication_types),
                "PubMed URL":
                    f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "Date Retrieved":
                    datetime.now(timezone.utc).date().isoformat()
            })

        time.sleep(0.4)

    return articles


def main():

    all_articles = {}

    for category, filter_query in CATEGORIES.items():

        print(f"Searching: {category}")

        query = f"{CARDIOLOGY} AND {filter_query}"

        pmids = search_pubmed(query)

        print(f"Found {len(pmids)} PMIDs")

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

    if DATA_FILE.exists():
        old_df = pd.read_csv(
            DATA_FILE,
            dtype=str
        ).fillna("")

        for _, row in old_df.iterrows():

            pmid = row["PMID"]

            if pmid not in all_articles:
                all_articles[pmid] = row.to_dict()

    if not all_articles:
        print("No publications found.")
        return

    df = pd.DataFrame(all_articles.values())

    df = df.drop_duplicates(subset=["PMID"])

    df = df.sort_values(
        by="PMID",
        ascending=False,
        key=lambda s: pd.to_numeric(s, errors="coerce")
    )

    df.to_csv(DATA_FILE, index=False)

    print(f"Saved {len(df)} publications")


if __name__ == "__main__":
    main()