import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="CardioEvidence",
    page_icon="❤️",
    layout="wide"
)

st.title("❤️ CardioEvidence")

st.markdown(
    "### Your Daily Cardiology Research Update"
)

st.write(
    "Automatically updated cardiology research "
    "from PubMed."
)

DATA_FILE = Path("publications.csv")

if not DATA_FILE.exists():
    st.warning(
        "No publications available yet. "
        "Run fetch_pubmed.py first."
    )
    st.stop()

df = pd.read_csv(DATA_FILE).fillna("")

# Sidebar
st.sidebar.title("Filters")

category = st.sidebar.selectbox(
    "Publication Type",
    [
        "All Studies",
        "Randomized Controlled Trials",
        "Observational Studies",
        "Guidelines & Statements"
    ]
)

search = st.sidebar.text_input(
    "Search by keyword"
)

journal = st.sidebar.selectbox(
    "Journal",
    ["All Journals"] + sorted(
        df["Journal"].dropna().unique().tolist()
    )
)

# Apply filters
filtered = df.copy()

if category != "All Studies":
    filtered = filtered[
        filtered["Category"].str.contains(
            category,
            case=False,
            na=False,
            regex=False
        )
    ]

if search:
    search_mask = (
        filtered["Title"].str.contains(
            search, case=False, na=False, regex=False
        )
        |
        filtered["Abstract"].str.contains(
            search, case=False, na=False, regex=False
        )
    )

    filtered = filtered[search_mask]

if journal != "All Journals":
    filtered = filtered[
        filtered["Journal"] == journal
    ]

# Dashboard metrics
col1, col2, col3 = st.columns(3)

col1.metric(
    "Total Publications",
    len(df)
)

col2.metric(
    "RCTs",
    df["Category"].str.contains(
        "Randomized Controlled Trials",
        regex=False
    ).sum()
)

col3.metric(
    "Guidelines & Statements",
    df["Category"].str.contains(
        "Guidelines & Statements",
        regex=False
    ).sum()
)

st.divider()

st.subheader(
    f"Publications ({len(filtered)})"
)

# Display articles
for _, article in filtered.iterrows():

    st.markdown(
        f"### {article['Title']}"
    )

    st.write(
        f"**Journal:** {article['Journal']}"
    )

    st.write(
        f"**Year:** {article['Year']}"
    )

    st.write(
        f"**Category:** {article['Category']}"
    )

    with st.expander("Read Abstract"):
        st.write(
            article["Abstract"]
            if article["Abstract"]
            else "Abstract not available."
        )

    st.link_button(
        "View on PubMed",
        article["PubMed URL"]
    )

    st.divider()

st.caption(
    "Source: PubMed / National Library of Medicine"
)