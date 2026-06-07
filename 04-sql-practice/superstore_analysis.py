"""
Superstore sales analysis: load CSV into SQLite and run business intelligence queries.
"""

import sqlite3

import pandas as pd

CSV_FILE = "Sample - Superstore.csv"
DB_NAME = "superstore.db"

# ---------------------------------------------------------------------------
# 1. Load CSV and create SQLite database
# ---------------------------------------------------------------------------
df = pd.read_csv(CSV_FILE, encoding="latin-1")

connection = sqlite3.connect(DB_NAME)
df.to_sql("sales", connection, if_exists="replace", index=False)

print(f"Loaded {len(df):,} rows from '{CSV_FILE}' into '{DB_NAME}'.\n")


def run_query(heading: str, sql: str) -> pd.DataFrame:
    """Run a SQL query and print results as a formatted table."""
    print("=" * 70)
    print(heading)
    print("-" * 70)
    result = pd.read_sql_query(sql, connection)
    print(result.to_string(index=False))
    print()
    return result


# ---------------------------------------------------------------------------
# 2. Run 8 analytical SQL queries
# ---------------------------------------------------------------------------

# Rank products by total profit and show how many orders each had.
query_1 = """
SELECT [Product Name],
       SUM(Profit) as total_profit,
       COUNT(*) as total_orders
FROM sales
GROUP BY [Product Name]
ORDER BY total_profit DESC
LIMIT 10
"""
run_query("Query 1 — Top 10 Most Profitable Products", query_1)

# Compare total sales, profit, and margin across product categories.
query_2 = """
SELECT Category,
       SUM(Sales) as total_sales,
       SUM(Profit) as total_profit,
       ROUND(SUM(Profit)/SUM(Sales)*100, 2) as profit_margin
FROM sales
GROUP BY Category
ORDER BY total_sales DESC
"""
run_query("Query 2 — Sales and Profit by Category", query_2)

# Find which region drives the most profit and how many unique customers it has.
query_3 = """
SELECT Region,
       SUM(Sales) as revenue,
       SUM(Profit) as profit,
       COUNT(DISTINCT [Customer ID]) as unique_customers
FROM sales
GROUP BY Region
ORDER BY profit DESC
"""
run_query("Query 3 — Which Region Is Most Profitable", query_3)

# Identify products that consistently lose money across all their orders.
query_4 = """
SELECT [Product Name],
       SUM(Profit) as total_loss,
       COUNT(*) as times_ordered
FROM sales
WHERE Profit < 0
GROUP BY [Product Name]
ORDER BY total_loss ASC
LIMIT 10
"""
run_query("Query 4 — Loss-Making Products (Profit < 0)", query_4)

# Break down customer count, revenue, and average order value by segment.
query_5 = """
SELECT Segment,
       COUNT(DISTINCT [Customer ID]) as customers,
       SUM(Sales) as revenue,
       AVG(Sales) as avg_order_value
FROM sales
GROUP BY Segment
"""
run_query("Query 5 — Customer Segment Performance", query_5)

# Track monthly revenue and order count for 2017 orders.
query_6 = """
SELECT substr([Order Date], 1, 7) as month,
       SUM(Sales) as monthly_revenue,
       COUNT(*) as orders
FROM sales
WHERE [Order Date] LIKE '2017%'
GROUP BY month
ORDER BY month
"""
run_query("Query 6 — Monthly Revenue Trend (2023)", query_6)

# Compare revenue, profit, and average discount across sub-categories.
query_7 = """
SELECT [Sub-Category],
       SUM(Sales) as revenue,
       SUM(Profit) as profit,
       AVG(Discount) as avg_discount
FROM sales
GROUP BY [Sub-Category]
ORDER BY profit DESC
"""
run_query("Query 7 — Sub-Category Profitability", query_7)

# List the top 10 customers by total lifetime spend.
query_8 = """
SELECT [Customer Name],
       [Customer ID],
       SUM(Sales) as lifetime_value,
       COUNT(*) as total_orders,
       AVG(Sales) as avg_order
FROM sales
GROUP BY [Customer ID]
ORDER BY lifetime_value DESC
LIMIT 10
"""
run_query("Query 8 — High Value Customers", query_8)

# ---------------------------------------------------------------------------
# 3. Business summary
# ---------------------------------------------------------------------------
summary_sql = """
SELECT
    ROUND(SUM(Sales), 2) AS total_revenue,
    ROUND(SUM(Profit), 2) AS total_profit,
    ROUND(SUM(Profit) / SUM(Sales) * 100, 2) AS profit_margin_pct
FROM sales
"""
totals = pd.read_sql_query(summary_sql, connection).iloc[0]

best_category = pd.read_sql_query(
    """
    SELECT Category
    FROM sales
    GROUP BY Category
    ORDER BY SUM(Profit) DESC
    LIMIT 1
    """,
    connection,
).iloc[0]["Category"]

best_region = pd.read_sql_query(
    """
    SELECT Region
    FROM sales
    GROUP BY Region
    ORDER BY SUM(Profit) DESC
    LIMIT 1
    """,
    connection,
).iloc[0]["Region"]

best_product = pd.read_sql_query(
    """
    SELECT [Product Name]
    FROM sales
    GROUP BY [Product Name]
    ORDER BY SUM(Profit) DESC
    LIMIT 1
    """,
    connection,
).iloc[0]["Product Name"]

print("=" * 70)
print("BUSINESS SUMMARY")
print("=" * 70)
print(f"  Total Revenue:           ${totals['total_revenue']:,.2f}")
print(f"  Total Profit:            ${totals['total_profit']:,.2f}")
print(f"  Overall Profit Margin:   {totals['profit_margin_pct']}%")
print(f"  Best Category:           {best_category}")
print(f"  Best Region:             {best_region}")
print(f"  Most Profitable Product: {best_product}")
print("=" * 70)

connection.close()
