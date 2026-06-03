"""AI Business Intelligence Bot — Streamlit app for CSV analysis and Claude reports."""

import io
import os
import zipfile
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

APP_DIR = Path(__file__).resolve().parent
SAMPLE_CSV = APP_DIR / "sample_sales.csv"

# ---------------------------------------------------------------------------
# Column detection helpers
# ---------------------------------------------------------------------------

DATE_KEYWORDS = ("date", "time", "day", "month", "year", "period")
REGION_KEYWORDS = ("region", "location", "city", "state", "country", "area", "territory", "zone")
CATEGORY_KEYWORDS = ("product", "category", "segment", "type", "class", "item", "sku", "name")
NUMERIC_PRIORITY = ("sales", "revenue", "amount", "value", "total", "price", "profit", "income")


def _col_lower(name: str) -> str:
    return str(name).lower().replace(" ", "_")


def detect_date_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if any(k in _col_lower(col) for k in DATE_KEYWORDS):
            return col
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() >= len(df) * 0.8:
                return col
        except (TypeError, ValueError):
            continue
    return None


def detect_region_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if any(k in _col_lower(col) for k in REGION_KEYWORDS):
            return col
    return None


def detect_category_column(df: pd.DataFrame, exclude: set[str]) -> str | None:
    for col in df.columns:
        if col in exclude:
            continue
        if any(k in _col_lower(col) for k in CATEGORY_KEYWORDS):
            if df[col].dtype == "object" or pd.api.types.is_string_dtype(df[col]):
                return col
    for col in df.columns:
        if col in exclude:
            continue
        if df[col].dtype == "object" or pd.api.types.is_string_dtype(df[col]):
            nunique = df[col].nunique()
            if 1 < nunique < len(df):
                return col
    return None


def get_numeric_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include="number").columns.tolist()


def pick_primary_numeric(df: pd.DataFrame) -> str | None:
    numeric = get_numeric_columns(df)
    if not numeric:
        return None
    for priority in NUMERIC_PRIORITY:
        for col in numeric:
            if priority in _col_lower(col):
                return col
    return numeric[0]


def pick_product_column(df: pd.DataFrame, exclude: set[str]) -> str | None:
    for col in df.columns:
        if col in exclude:
            continue
        if "product" in _col_lower(col):
            return col
    return detect_category_column(df, exclude)


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Parse dates and coerce numeric columns where possible."""
    out = df.copy()
    date_col = detect_date_column(out)
    if date_col and not pd.api.types.is_datetime64_any_dtype(out[date_col]):
        out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    return out


# ---------------------------------------------------------------------------
# Chart builders (matplotlib) — return Figure objects
# ---------------------------------------------------------------------------


def chart_line_over_time(df: pd.DataFrame, date_col: str, value_col: str) -> plt.Figure | None:
    try:
        plot_df = df[[date_col, value_col]].dropna().copy()
        plot_df = plot_df.sort_values(date_col)
        plot_df = plot_df.groupby(date_col, as_index=False)[value_col].sum()

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(plot_df[date_col], plot_df[value_col], marker="o", linewidth=2, color="#2563eb")
        ax.set_xlabel(date_col)
        ax.set_ylabel(value_col)
        ax.set_title(f"{value_col} Over Time")
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        plt.tight_layout()
        return fig
    except Exception:
        plt.close("all")
        return None


def chart_bar_by_column(df: pd.DataFrame, group_col: str, value_col: str, title: str) -> plt.Figure | None:
    try:
        grouped = df.groupby(group_col, as_index=False)[value_col].sum()
        grouped = grouped.sort_values(value_col, ascending=False)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(grouped[group_col].astype(str), grouped[value_col], color="#059669")
        ax.set_xlabel(group_col)
        ax.set_ylabel(value_col)
        ax.set_title(title)
        plt.xticks(rotation=45, ha="right")
        ax.grid(True, axis="y", alpha=0.3)
        plt.tight_layout()
        return fig
    except Exception:
        plt.close("all")
        return None


def chart_top_records(df: pd.DataFrame, value_col: str, n: int = 5) -> plt.Figure | None:
    try:
        top = df.nlargest(n, value_col)
        label_cols = [c for c in df.columns if c != value_col][:3]
        labels = top[label_cols].astype(str).agg(" | ".join, axis=1) if label_cols else top.index.astype(str)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.barh(range(len(top)), top[value_col].values, color="#7c3aed")
        ax.set_yticks(range(len(top)))
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_xlabel(value_col)
        ax.set_title(f"Top {n} Records by {value_col}")
        ax.grid(True, axis="x", alpha=0.3)
        plt.tight_layout()
        return fig
    except Exception:
        plt.close("all")
        return None


def build_charts(df: pd.DataFrame) -> list[tuple[str, plt.Figure]]:
    """Build up to 4 charts; returns list of (filename, figure)."""
    charts: list[tuple[str, plt.Figure]] = []
    df = prepare_dataframe(df)
    value_col = pick_primary_numeric(df)
    if not value_col:
        return charts

    date_col = detect_date_column(df)
    region_col = detect_region_column(df)
    exclude = {c for c in (date_col, region_col) if c}
    category_col = detect_category_column(df, exclude)

    if date_col:
        fig = chart_line_over_time(df, date_col, value_col)
        if fig:
            charts.append(("chart1_line_over_time.png", fig))

    if category_col:
        fig = chart_bar_by_column(
            df, category_col, value_col, f"Total {value_col} by {category_col}"
        )
        if fig:
            charts.append(("chart2_by_category.png", fig))

    if region_col:
        fig = chart_bar_by_column(
            df, region_col, value_col, f"Total {value_col} by {region_col}"
        )
        if fig:
            charts.append(("chart3_by_region.png", fig))

    fig = chart_top_records(df, value_col)
    if fig:
        charts.append(("chart4_top5_records.png", fig))

    return charts


def fig_to_bytes(fig: plt.Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()


def charts_to_zip(chart_list: list[tuple[str, plt.Figure]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, fig in chart_list:
            zf.writestr(name, fig_to_bytes(fig))
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# AI report
# ---------------------------------------------------------------------------


def categorical_totals(df: pd.DataFrame) -> str:
    numeric = get_numeric_columns(df)
    if not numeric:
        return "No numeric columns for aggregation."
    value_col = pick_primary_numeric(df)
    lines = []
    cat_cols = df.select_dtypes(include=["object", "string", "category"]).columns
    for col in cat_cols:
        try:
            grouped = df.groupby(col)[value_col].sum().sort_values(ascending=False)
            lines.append(f"\n### Total {value_col} by {col}\n{grouped.to_string()}")
        except Exception:
            continue
    return "\n".join(lines) if lines else "No categorical columns found."


def build_claude_prompt(df: pd.DataFrame) -> str:
    describe_str = df.describe(include="all").to_string()
    cat_totals = categorical_totals(df)

    data_context = f"""
Dataset shape: {df.shape[0]} rows, {df.shape[1]} columns

Column names: {', '.join(df.columns.astype(str))}

Summary statistics:
{describe_str}

Top 5 rows:
{df.head().to_string()}

Bottom 5 rows:
{df.tail().to_string()}

Totals by categorical columns:
{cat_totals}
"""

    return f"""You are a senior business analyst. Analyze this dataset and write a professional executive report.

{data_context}

Structure your report as:
## Executive Summary (3-4 sentences)
## Key Findings (5 bullet points with specific numbers)
## Trends & Patterns (what's growing, what's declining)
## Top Performers (best product/region/segment)
## Recommendations (3 specific, actionable suggestions)
## Risk Areas (2-3 things to watch out for)

Be specific — use actual numbers from the data.
Write as if presenting to a CEO."""


def generate_ai_report(df: pd.DataFrame) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found. Add it to your .env file."
        )

    client = Anthropic(api_key=api_key)
    prompt = build_claude_prompt(df)

    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def get_dataset_context(df: pd.DataFrame) -> str:
    describe_str = df.describe(include="all").to_string()
    cat_totals = categorical_totals(df)
    return f"""
Dataset shape: {df.shape[0]} rows, {df.shape[1]} columns

Column names: {', '.join(df.columns.astype(str))}

Summary statistics:
{describe_str}

Top 5 rows:
{df.head().to_string()}

Bottom 5 rows:
{df.tail().to_string()}

Totals by categorical columns:
{cat_totals}
"""


def answer_data_question(df: pd.DataFrame, question: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found. Add it to your .env file.")

    prompt = f"""You are a senior business analyst with access to this dataset.

{get_dataset_context(df)}

User question: {question}

Answer the question using only the data provided above. Be specific with numbers.
If the data cannot answer the question, say what is missing and suggest what column would help."""

    client = Anthropic(api_key=api_key)
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def compute_kpi_metrics(df: pd.DataFrame) -> dict[str, str]:
    """Return display-ready KPI values for the metric row."""
    value_col = pick_primary_numeric(df)
    date_col = detect_date_column(df)
    region_col = detect_region_column(df)
    exclude = {c for c in (date_col, region_col) if c}
    product_col = pick_product_column(df, exclude)

    total_revenue = "N/A"
    if value_col:
        total = pd.to_numeric(df[value_col], errors="coerce").sum()
        total_revenue = f"${total:,.0f}" if "sales" in _col_lower(value_col) or "revenue" in _col_lower(value_col) else f"{total:,.0f}"

    best_month = "N/A"
    if date_col and value_col:
        monthly = df.copy()
        monthly["_month"] = pd.to_datetime(monthly[date_col], errors="coerce").dt.to_period("M")
        by_month = monthly.groupby("_month")[value_col].sum()
        if not by_month.empty:
            best_month = str(by_month.idxmax())

    best_product = "N/A"
    if product_col and value_col:
        by_product = df.groupby(product_col)[value_col].sum()
        if not by_product.empty:
            best_product = str(by_product.idxmax())

    return {
        "total_revenue": total_revenue,
        "best_month": best_month,
        "best_product": best_product,
        "total_records": f"{len(df):,}",
    }


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------


def render_sidebar() -> None:
    st.sidebar.title("About")
    st.sidebar.markdown(
        """
        **AI Business Intelligence Bot** turns raw CSV exports into
        instant dashboards and executive-ready AI reports.

        Upload sales, marketing, finance, or operations data — no setup required.
        """
    )
    st.sidebar.markdown("---")
    st.sidebar.subheader("How it works")
    st.sidebar.markdown(
        """
        1. **Upload** your CSV file in the main area
        2. **Explore** automatic previews, stats, and charts
        3. **Generate** an AI executive report with one click
        """
    )
    st.sidebar.markdown("---")
    if SAMPLE_CSV.exists():
        st.sidebar.download_button(
            label="📥 Download Sample CSV",
            data=SAMPLE_CSV.read_bytes(),
            file_name="sample_sales.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.sidebar.warning("Sample CSV not found on disk.")


def render_data_overview(df: pd.DataFrame) -> None:
    st.subheader("📋 Data Preview")
    st.dataframe(df.head(5), use_container_width=True)

    st.markdown(
        f"**Dataset shape:** {df.shape[0]:,} rows × {df.shape[1]} columns"
    )

    st.subheader("Column Types")
    dtype_df = pd.DataFrame(
        {"Column": df.columns, "Data Type": df.dtypes.astype(str).values}
    )
    st.dataframe(dtype_df, use_container_width=True, hide_index=True)

    numeric_cols = get_numeric_columns(df)
    if numeric_cols:
        st.subheader("📈 Basic Statistics (Numeric Columns)")
        stats_rows = []
        for col in numeric_cols:
            series = pd.to_numeric(df[col], errors="coerce")
            stats_rows.append(
                {
                    "Column": col,
                    "Sum": series.sum(),
                    "Mean": series.mean(),
                    "Min": series.min(),
                    "Max": series.max(),
                }
            )
        stats_df = pd.DataFrame(stats_rows)
        for col in ("Sum", "Mean", "Min", "Max"):
            stats_df[col] = stats_df[col].round(2)
        st.dataframe(stats_df, use_container_width=True, hide_index=True)


def render_metric_row(df: pd.DataFrame) -> None:
    kpis = compute_kpi_metrics(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Revenue", kpis["total_revenue"])
    c2.metric("Best Month", kpis["best_month"])
    c3.metric("Best Product", kpis["best_product"])
    c4.metric("Total Records", kpis["total_records"])


def render_charts(df: pd.DataFrame) -> list[tuple[str, plt.Figure]]:
    chart_list = build_charts(df)

    if not chart_list:
        st.info("No suitable columns detected for charts. Ensure you have numeric and categorical/date columns.")
        return []

    for name, fig in chart_list:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    return chart_list


def render_downloads(df: pd.DataFrame) -> None:
    st.subheader("⬇️ Downloads")
    col1, col2 = st.columns(2)

    with col1:
        if st.session_state.get("ai_report"):
            st.download_button(
                label="📄 Download Report",
                data=st.session_state["ai_report"],
                file_name="ai_executive_report.txt",
                mime="text/plain",
                use_container_width=True,
            )
        else:
            st.caption("Generate a report first to download.")

    with col2:
        fresh_charts = build_charts(df)
        if fresh_charts:
            st.download_button(
                label="🖼️ Download Charts (ZIP)",
                data=charts_to_zip(fresh_charts),
                file_name="bi_charts.zip",
                mime="application/zip",
                use_container_width=True,
            )
        else:
            st.caption("No charts available to download.")


def render_ai_report_tab(df: pd.DataFrame) -> None:
    st.subheader("🤖 AI Executive Report")

    if st.button("🤖 Generate AI Report", type="primary", use_container_width=True):
        try:
            with st.spinner("Claude is analyzing your data..."):
                st.session_state["ai_report"] = generate_ai_report(df)
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"AI analysis failed: {e}")
            st.caption("Check your API key, network connection, and try again.")

    if st.session_state.get("ai_report"):
        st.markdown(st.session_state["ai_report"])
        st.markdown("---")
        render_downloads(df)

        st.markdown("---")
        st.subheader("💬 Ask a Question")
        st.caption('Example: "Which month had the highest sales?"')
        follow_up = st.text_input(
            "Question about your data",
            key="report_follow_up_question",
            placeholder="Which month had highest sales?",
            label_visibility="collapsed",
        )
        if st.button("Get Answer", key="report_follow_up_btn"):
            if not follow_up.strip():
                st.warning("Please enter a question.")
            else:
                try:
                    with st.spinner("Claude is thinking..."):
                        answer = answer_data_question(df, follow_up.strip())
                    st.session_state["last_qa"] = (follow_up.strip(), answer)
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Could not get an answer: {e}")

        if st.session_state.get("last_qa"):
            q, a = st.session_state["last_qa"]
            st.markdown(f"**Q:** {q}")
            st.markdown(a)


def render_ask_claude_tab(df: pd.DataFrame) -> None:
    st.subheader("💬 Ask Claude About Your Data")
    st.markdown(
        "Ask anything about your uploaded dataset. Claude answers using your "
        "data preview, statistics, and category totals."
    )

    question = st.text_input(
        "Your question",
        placeholder='e.g. "Which month had highest sales?"',
        key="ask_claude_question",
    )

    if st.button("🔍 Ask Claude", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            try:
                with st.spinner("Claude is thinking..."):
                    answer = answer_data_question(df, question.strip())
                st.session_state["last_qa"] = (question.strip(), answer)
                st.session_state.setdefault("qa_history", []).append(
                    (question.strip(), answer)
                )
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Could not get an answer: {e}")

    if st.session_state.get("qa_history"):
        st.markdown("---")
        for q, a in reversed(st.session_state["qa_history"]):
            st.markdown(f"**Q:** {q}")
            st.markdown(a)
            st.markdown("---")


def main() -> None:
    st.set_page_config(
        page_title="AI Business Intelligence Bot",
        page_icon="📊",
        layout="wide",
    )

    st.title("📊 AI Business Intelligence Bot")
    st.caption("Upload any CSV — Get instant AI analysis")

    render_sidebar()

    uploaded = st.file_uploader(
        "Upload your CSV file",
        type=["csv"],
        help="Drag and drop or browse to select a CSV file.",
    )

    if uploaded is None:
        st.info("👆 Upload a CSV file to begin analysis, or download the sample from the sidebar.")
        return

    try:
        with st.spinner("Loading and parsing your data..."):
            df = pd.read_csv(uploaded)
            if df.empty:
                st.error("The uploaded file is empty. Please upload a CSV with data.")
                return
            df = prepare_dataframe(df)
            st.session_state.pop("ai_report", None)
            st.session_state.pop("last_qa", None)
            st.session_state.pop("qa_history", None)
    except pd.errors.EmptyDataError:
        st.error("The CSV file appears to be empty or invalid.")
        return
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        return

    st.success(f"Loaded **{uploaded.name}** successfully.")
    render_metric_row(df)
    st.session_state["dataframe"] = df

    tab_overview, tab_charts, tab_report, tab_ask = st.tabs(
        ["📈 Data Overview", "📊 Charts", "🤖 AI Report", "💬 Ask Claude"]
    )

    with tab_overview:
        render_data_overview(df)

    with tab_charts:
        st.session_state["chart_list"] = render_charts(df)

    with tab_report:
        render_ai_report_tab(df)

    with tab_ask:
        render_ask_claude_tab(df)


if __name__ == "__main__":
    main()
