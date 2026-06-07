"""
Superstore AI analysis: run SQL queries on superstore.db and get Claude business insights.
"""

import os
import sqlite3

import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

DB_NAME = "superstore.db"

QUERIES = [
    (
        "Query 1 — Top 10 Most Profitable Products",
        """
        SELECT [Product Name],
               SUM(Profit) as total_profit,
               COUNT(*) as total_orders
        FROM sales
        GROUP BY [Product Name]
        ORDER BY total_profit DESC
        LIMIT 10
        """,
    ),
    (
        "Query 2 — Sales and Profit by Category",
        """
        SELECT Category,
               SUM(Sales) as total_sales,
               SUM(Profit) as total_profit,
               ROUND(SUM(Profit)/SUM(Sales)*100, 2) as profit_margin
        FROM sales
        GROUP BY Category
        ORDER BY total_sales DESC
        """,
    ),
    (
        "Query 3 — Which Region Is Most Profitable",
        """
        SELECT Region,
               SUM(Sales) as revenue,
               SUM(Profit) as profit,
               COUNT(DISTINCT [Customer ID]) as unique_customers
        FROM sales
        GROUP BY Region
        ORDER BY profit DESC
        """,
    ),
    (
        "Query 4 — Loss-Making Products (Profit < 0)",
        """
        SELECT [Product Name],
               SUM(Profit) as total_loss,
               COUNT(*) as times_ordered
        FROM sales
        WHERE Profit < 0
        GROUP BY [Product Name]
        ORDER BY total_loss ASC
        LIMIT 10
        """,
    ),
    (
        "Query 5 — Customer Segment Performance",
        """
        SELECT Segment,
               COUNT(DISTINCT [Customer ID]) as customers,
               SUM(Sales) as revenue,
               AVG(Sales) as avg_order_value
        FROM sales
        GROUP BY Segment
        """,
    ),
    (
        "Query 6 — Monthly Revenue Trend (2023)",
        """
        SELECT substr([Order Date], 1, 7) as month,
               SUM(Sales) as monthly_revenue,
               COUNT(*) as orders
        FROM sales
        WHERE [Order Date] LIKE '2017%'
        GROUP BY month
        ORDER BY month
        """,
    ),
    (
        "Query 7 — Sub-Category Profitability",
        """
        SELECT [Sub-Category],
               SUM(Sales) as revenue,
               SUM(Profit) as profit,
               AVG(Discount) as avg_discount
        FROM sales
        GROUP BY [Sub-Category]
        ORDER BY profit DESC
        """,
    ),
    (
        "Query 8 — High Value Customers",
        """
        SELECT [Customer Name],
               [Customer ID],
               SUM(Sales) as lifetime_value,
               COUNT(*) as total_orders,
               AVG(Sales) as avg_order
        FROM sales
        GROUP BY [Customer ID]
        ORDER BY lifetime_value DESC
        LIMIT 10
        """,
    ),
]


def run_all_queries(connection: sqlite3.Connection) -> str:
    """Run all 8 queries and return results as one formatted string."""
    sections = []

    for heading, sql in QUERIES:
        df = pd.read_sql_query(sql, connection)
        sections.append(f"{heading}\n{df.to_string(index=False)}")

    return "\n\n".join(sections)


def build_analysis_prompt(query_results: str) -> str:
    """Build the prompt sent to Claude for business analysis."""
    return f"""You are a senior retail business analyst.
I'm giving you SQL query results from a US retail superstore dataset (4 years of data, ~10,000 orders).

Analyze these results and give me:

## 🔴 Critical Problems (top 3 issues hurting profit)
## 🟢 Growth Opportunities (top 3 things to double down on)
## 💡 Quick Wins (3 things they can do immediately)
## 📊 KPIs to Track (5 metrics this business must monitor)
## 🎯 6-Month Strategy (what should they focus on)

Be specific — use actual numbers from the data.
Think like a McKinsey consultant.

--- QUERY RESULTS ---

{query_results}"""


def get_claude_analysis(client: Anthropic, query_results: str) -> str:
    """Send query results to Claude and return the business analysis."""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": build_analysis_prompt(query_results)}],
    )
    return response.content[0].text


def main() -> None:
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found. Add it to your .env file.")

    if not os.path.exists(DB_NAME):
        raise FileNotFoundError(
            f"'{DB_NAME}' not found. Run superstore_analysis.py first to create the database."
        )

    connection = sqlite3.connect(DB_NAME)

    print("Running 8 SQL queries on superstore.db...\n")
    query_results = run_all_queries(connection)
    connection.close()

    print("Sending results to Claude for analysis...\n")
    client = Anthropic(api_key=api_key)
    analysis = get_claude_analysis(client, query_results)

    print("=" * 70)
    print("SUPERSTORE BUSINESS ANALYSIS (Claude)")
    print("=" * 70)
    print()
    print(analysis)
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
