import time
from io import StringIO

import pandas as pd
import streamlit as st
from anthropic import Anthropic

from lead_qualifier import DELAY_SECONDS, load_api_key, qualify_company

REQUIRED_COLUMNS = {"company_name", "industry", "size"}
OUTPUT_COLUMNS = [
    "company_name",
    "industry",
    "size",
    "score",
    "reason",
    "best_use_case",
]

SAMPLE_CSV = """company_name,industry,size
Zomato,Food Delivery,Large
Razorpay,Fintech,Medium
Meesho,E-commerce,Large
"""


def validate_columns(df: pd.DataFrame) -> list[str]:
    return sorted(REQUIRED_COLUMNS - set(df.columns))


def score_color_label(score) -> str:
    if pd.isna(score):
        return ""
    try:
        value = int(score)
    except (TypeError, ValueError):
        return ""
    if value >= 8:
        return "High"
    if value >= 5:
        return "Medium"
    return "Low"


def style_results_df(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.copy()
    display_df["Score Color"] = display_df["score"].apply(score_color_label)
    return display_df


def process_leads(df: pd.DataFrame, client: Anthropic, progress_bar) -> pd.DataFrame:
    results = []
    rows = df.to_dict(orient="records")
    total = len(rows)

    for index, row in enumerate(rows):
        company_name = str(row["company_name"]).strip()
        industry = str(row["industry"]).strip()
        size = str(row["size"]).strip()

        result_row = {
            "company_name": company_name,
            "industry": industry,
            "size": size,
            "score": None,
            "reason": "",
            "best_use_case": "",
        }

        try:
            parsed = qualify_company(client, company_name, industry, size)
            result_row["score"] = parsed["score"]
            result_row["reason"] = parsed["reason"]
            result_row["best_use_case"] = parsed["best_use_case"]
        except Exception as exc:
            result_row["reason"] = f"Error: {exc}"

        results.append(result_row)
        progress_bar.progress((index + 1) / total)

        if index < total - 1:
            time.sleep(DELAY_SECONDS)

    return pd.DataFrame(results, columns=OUTPUT_COLUMNS)


def render_summary_metrics(df: pd.DataFrame) -> None:
    valid = df.dropna(subset=["score"]).copy()
    top_industry = "—"
    avg_display = "—"

    if not valid.empty:
        valid["score"] = valid["score"].astype(int)
        avg_display = f"{valid['score'].mean():.1f}"
        industry_avg = valid.groupby("industry")["score"].mean()
        top_industry = industry_avg.idxmax()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Leads", len(df))
    col2.metric("Average Score", avg_display)
    col3.metric("Top Industry", top_industry)


def render_top_leads(df: pd.DataFrame) -> None:
    valid = df.dropna(subset=["score"]).copy()
    if valid.empty:
        st.warning("No successfully scored leads to highlight.")
        return

    valid["score"] = valid["score"].astype(int)
    top3 = valid.nlargest(3, "score")

    st.subheader("Top 3 leads")
    cols = st.columns(3)
    for col, (_, row) in zip(cols, top3.iterrows()):
        with col:
            st.markdown(f"### {row['company_name']}")
            st.metric("Lead score", f"{row['score']}/10")
            st.caption(f"{row['industry']} · {row['size']}")
            st.markdown(f"**Best use case:** {row['best_use_case']}")


def display_results(results_df: pd.DataFrame) -> None:
    render_summary_metrics(results_df)
    st.subheader("Qualification results")
    st.dataframe(style_results_df(results_df), use_container_width=True)

    render_top_leads(results_df)

    chart_df = results_df.dropna(subset=["score"]).copy()
    if not chart_df.empty:
        chart_df["score"] = chart_df["score"].astype(int)
        st.subheader("Scores by company")
        st.bar_chart(
            chart_df.set_index("company_name")["score"],
            use_container_width=True,
        )

    csv_buffer = StringIO()
    results_df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="Download results CSV",
        data=csv_buffer.getvalue(),
        file_name="qualified_leads.csv",
        mime="text/csv",
        type="primary",
    )


def main() -> None:
    st.set_page_config(
        page_title="AI Lead Qualifier Agent",
        page_icon="🎯",
        layout="wide",
    )

    st.title("🎯 AI Lead Qualifier Agent")
    st.caption("Powered by Claude AI")

    with st.sidebar:
        st.header("How to use")
        st.markdown(
            """
            1. Prepare a CSV with columns: **company_name**, **industry**, **size**
            2. Upload your file below
            3. Click **Qualify Leads**
            4. Review scores, top leads, and the chart
            5. Download your qualified leads CSV
            """
        )
        st.divider()
        st.markdown("Built with n8n + Claude API + Python")

    st.download_button(
        label="Download sample CSV",
        data=SAMPLE_CSV,
        file_name="sample_leads.csv",
        mime="text/csv",
        help="Example format: company_name, industry, size",
    )

    uploaded = st.file_uploader(
        "Upload your leads CSV",
        type=["csv"],
        help="Required columns: company_name, industry, size",
    )

    if uploaded is None:
        st.info("Upload a CSV file to get started.")
        return

    file_key = f"{uploaded.name}:{uploaded.size}"
    if st.session_state.get("upload_file_key") != file_key:
        st.session_state["upload_file_key"] = file_key
        st.session_state.pop("results_df", None)

    try:
        input_df = pd.read_csv(uploaded)
    except Exception as exc:
        st.error(f"Could not read CSV file: {exc}")
        return

    missing = validate_columns(input_df)
    if missing:
        st.error(
            f"Your CSV is missing required columns: **{', '.join(missing)}**. "
            f"Expected: company_name, industry, size"
        )
        return

    st.markdown(f"**{len(input_df)}** companies loaded and ready to qualify.")

    qualify_clicked = st.button("Qualify Leads", type="primary")

    if qualify_clicked:
        try:
            api_key = load_api_key()
        except ValueError:
            st.error(
                "**API key missing.** Add `ANTHROPIC_API_KEY=your_key_here` to a `.env` "
                "file in the project folder (same folder as this app), then refresh the page."
            )
            return

        client = Anthropic(api_key=api_key)
        progress_bar = st.progress(0)

        with st.spinner("Claude is analyzing your leads..."):
            try:
                results_df = process_leads(input_df, client, progress_bar)
            except Exception as exc:
                st.error(f"Something went wrong while qualifying leads: {exc}")
                return

        progress_bar.empty()
        st.session_state["results_df"] = results_df
        st.success(f"Finished qualifying {len(results_df)} leads.")

    if "results_df" in st.session_state:
        display_results(st.session_state["results_df"])
    else:
        with st.expander("Preview uploaded data"):
            st.dataframe(input_df, use_container_width=True)


if __name__ == "__main__":
    main()
