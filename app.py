import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="CardioEvidence",
    page_icon="❤️",
    layout="wide"
)

st.title("❤️ CardioEvidence")

st.markdown("### Your Daily Cardiology Research Update")

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

# Load publications
df = pd.read_csv(DATA_FILE).fillna("")

# Convert dates
for column in ["Publication Date", "PubMed Entry Date"]:
    if column not in df.columns:
        df[column] = ""

    df[column] = pd.to_datetime(
        df[column],
        errors="coerce"
    )

# -----------------------------
# SIDEBAR FILTERS
# -----------------------------

st.sidebar.title("Filters")

date_filter = st.sidebar.selectbox(
    "Date Range",
    [
        "All Publications",
        "Today",
        "Last 7 Days",
        "Last 30 Days"
    ]
)

date_type = st.sidebar.radio(
    "Filter by",
    [
        "PubMed Entry Date",
        "Publication Date"
    ]
)

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
        df["Journal"].astype(str).unique().tolist()
    )
)

# -----------------------------
# APPLY FILTERS
# -----------------------------

filtered = df.copy()

today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()

if date_filter == "Today":
    cutoff = today

elif date_filter == "Last 7 Days":
    cutoff = today - pd.Timedelta(days=6)

elif date_filter == "Last 30 Days":
    cutoff = today - pd.Timedelta(days=29)

else:
    cutoff = None

if cutoff is not None:
    filtered = filtered[
        (filtered[date_type] >= cutoff)
        & (filtered[date_type] < today + pd.Timedelta(days=1))
    ]

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
            search,
            case=False,
            na=False,
            regex=False
        )
        |
        filtered["Abstract"].str.contains(
            search,
            case=False,
            na=False,
            regex=False
        )
    )

    filtered = filtered[search_mask]

if journal != "All Journals":
    filtered = filtered[
        filtered["Journal"] == journal
    ]

# -----------------------------
# SORT NEWEST FIRST
# -----------------------------

sort_by = st.sidebar.selectbox(
    "Sort Publications By",
    [
        "Newest PubMed Entry",
        "Newest Publication Date"
    ]
)

if sort_by == "Newest Publication Date":
    sort_column = "Publication Date"
else:
    sort_column = "PubMed Entry Date"

filtered = filtered.sort_values(
    by=[sort_column, "PMID"],
    ascending=[False, False],
    na_position="last"
)

# -----------------------------
# PAGINATION
# -----------------------------

results_per_page = st.sidebar.selectbox(
    "Results Per Page",
    [25, 50, 100],
    index=0
)

total_results = len(filtered)

total_pages = max(
    1,
    (total_results + results_per_page - 1)
    // results_per_page
)

# Track the current page
if "page" not in st.session_state:
    st.session_state.page = 1

# Reset to page 1 when filters change
filter_signature = (
    date_filter,
    date_type,
    category,
    search,
    journal,
    sort_by,
    results_per_page
)

if st.session_state.get("last_filter_signature") != filter_signature:
    st.session_state.page = 1
    st.session_state.last_filter_signature = filter_signature

# Ensure the page is valid
st.session_state.page = min(
    max(1, st.session_state.page),
    total_pages
)

# Select only the articles for this page
start_index = (
    st.session_state.page - 1
) * results_per_page

end_index = start_index + results_per_page

page_articles = filtered.iloc[
    start_index:end_index
]

# -----------------------------
# DASHBOARD METRICS
# -----------------------------

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
    f"Publications ({total_results})"
)

# -----------------------------
# PAGE NAVIGATION
# -----------------------------

def page_navigation(location):

    col1, col2, col3 = st.columns(
        [1, 2, 1]
    )

    with col1:
        if st.button(
            "⬅ Previous",
            disabled=st.session_state.page == 1,
            key=f"previous_{location}"
        ):
            st.session_state.page -= 1
            st.rerun()

    with col2:
        st.markdown(
            f"<div style='text-align:center;'>"
            f"<strong>Page {st.session_state.page} "
            f"of {total_pages}</strong>"
            f"</div>",
            unsafe_allow_html=True
        )

    with col3:
        if st.button(
            "Next ➡",
            disabled=st.session_state.page == total_pages,
            key=f"next_{location}"
        ):
            st.session_state.page += 1
            st.rerun()


page_navigation("top")

st.divider()

# -----------------------------
# DISPLAY ARTICLES
# -----------------------------

if total_results == 0:
    st.info(
        "No publications match your filters. "
        "Try changing your search criteria."
    )

else:
    for _, article in page_articles.iterrows():

        st.markdown(
            f"### {article['Title']}"
        )

        st.write(
            f"**Journal:** {article['Journal']}"
        )

        st.write(
            f"**Year:** {article['Year']}"
        )

        publication_date = article["Publication Date"]
        entry_date = article["PubMed Entry Date"]

        if pd.notna(publication_date):
            st.write(
                f"**Published:** "
                f"{publication_date.strftime('%B %d, %Y')}"
            )

        if pd.notna(entry_date):
            st.write(
                f"**Added to PubMed:** "
                f"{entry_date.strftime('%B %d, %Y')}"
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

# -----------------------------
# BOTTOM NAVIGATION
# -----------------------------

page_navigation("bottom")

st.caption(
    "Source: PubMed / National Library of Medicine"
)