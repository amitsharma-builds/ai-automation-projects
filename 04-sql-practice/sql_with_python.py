"""
SQLite sales database demo: create sample data and run analytical SQL queries via pandas.
"""

import sqlite3

import pandas as pd

DB_NAME = "sales.db"

# ---------------------------------------------------------------------------
# 1. Create database and sales table
# ---------------------------------------------------------------------------
connection = sqlite3.connect(DB_NAME)
cursor = connection.cursor()

cursor.execute("DROP TABLE IF EXISTS sales")

cursor.execute(
    """
    CREATE TABLE sales (
        id      INTEGER PRIMARY KEY,
        date    TEXT    NOT NULL,
        product TEXT    NOT NULL,
        region  TEXT    NOT NULL,
        amount  REAL    NOT NULL,
        units   INTEGER NOT NULL,
        segment TEXT    NOT NULL
    )
    """
)

# ---------------------------------------------------------------------------
# 2. Insert 20 rows of realistic Indian business sales data
# ---------------------------------------------------------------------------
sample_sales = [
    (1, "2024-01-15", "Product A", "North", 78500.00, 42, "Enterprise"),
    (2, "2024-01-22", "Product B", "South", 45200.00, 28, "SMB"),
    (3, "2024-02-03", "Product C", "West",  62300.00, 35, "Startup"),
    (4, "2024-02-14", "Product A", "East",  91800.00, 51, "Enterprise"),
    (5, "2024-02-28", "Product B", "North", 38750.00, 22, "SMB"),
    (6, "2024-03-08", "Product C", "South", 55600.00, 31, "Startup"),
    (7, "2024-03-19", "Product A", "West",  84200.00, 47, "Enterprise"),
    (8, "2024-03-25", "Product B", "East",  29400.00, 18, "SMB"),
    (9, "2024-04-05", "Product C", "North", 67800.00, 38, "Enterprise"),
    (10, "2024-04-12", "Product A", "South", 73500.00, 40, "SMB"),
    (11, "2024-04-20", "Product B", "West",  51200.00, 29, "Startup"),
    (12, "2024-05-02", "Product C", "East",  48900.00, 27, "SMB"),
    (13, "2024-05-15", "Product A", "North", 96500.00, 55, "Enterprise"),
    (14, "2024-05-28", "Product B", "South", 41800.00, 24, "Startup"),
    (15, "2024-06-10", "Product C", "West",  73200.00, 41, "Enterprise"),
    (16, "2024-06-18", "Product A", "East",  58700.00, 33, "SMB"),
    (17, "2024-06-25", "Product B", "North", 35600.00, 20, "Startup"),
    (18, "2024-07-03", "Product C", "South", 81400.00, 46, "Enterprise"),
    (19, "2024-07-14", "Product A", "West",  69800.00, 39, "SMB"),
    (20, "2024-07-22", "Product B", "East",  47250.00, 26, "Startup"),
]

cursor.executemany(
    """
    INSERT INTO sales (id, date, product, region, amount, units, segment)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    sample_sales,
)
connection.commit()

print(f"Created '{DB_NAME}' with {len(sample_sales)} sales records.\n")
print("=" * 70)


def run_query(title: str, explanation: str, sql: str) -> None:
    """Run a SQL query via pandas and print a formatted table."""
    print(f"\n{title}")
    print("-" * 70)
    print(f"Plain English: {explanation}\n")
    df = pd.read_sql_query(sql, connection)
    print(df.to_string(index=False))
    print()


# ---------------------------------------------------------------------------
# Query 1: Total revenue by product (sorted high to low)
# ---------------------------------------------------------------------------
# Sum all sale amounts for each product, then sort from highest to lowest revenue.
query_1 = """
SELECT
    product,
    ROUND(SUM(amount), 2) AS total_revenue
FROM sales
GROUP BY product
ORDER BY total_revenue DESC
"""

run_query(
    "Query 1: Total Revenue by Product",
    "Add up every sale amount grouped by product, showing which product earns the most.",
    query_1,
)

# ---------------------------------------------------------------------------
# Query 2: Average deal size by customer segment
# ---------------------------------------------------------------------------
# Calculate the mean transaction amount for Enterprise, SMB, and Startup customers.
query_2 = """
SELECT
    segment,
    ROUND(AVG(amount), 2) AS avg_deal_size
FROM sales
GROUP BY segment
ORDER BY avg_deal_size DESC
"""

run_query(
    "Query 2: Average Deal Size by Customer Segment",
    "Find the typical transaction value for each customer type (Enterprise, SMB, Startup).",
    query_2,
)

# ---------------------------------------------------------------------------
# Query 3: Top 5 highest value transactions
# ---------------------------------------------------------------------------
# List the five individual sales with the largest amounts.
query_3 = """
SELECT
    id,
    date,
    product,
    region,
    amount,
    units,
    segment
FROM sales
ORDER BY amount DESC
LIMIT 5
"""

run_query(
    "Query 3: Top 5 Highest Value Transactions",
    "Show the five biggest single deals in the dataset, ranked by amount.",
    query_3,
)

# ---------------------------------------------------------------------------
# Query 4: Monthly revenue trend
# ---------------------------------------------------------------------------
# Extract year-month from each date and sum revenue per month to spot trends.
query_4 = """
SELECT
    strftime('%Y-%m', date) AS month,
    ROUND(SUM(amount), 2) AS monthly_revenue
FROM sales
GROUP BY strftime('%Y-%m', date)
ORDER BY month
"""

run_query(
    "Query 4: Monthly Revenue Trend",
    "Group sales by calendar month and total revenue to see how business grows over time.",
    query_4,
)

# ---------------------------------------------------------------------------
# Query 5: Region + product combination with most revenue
# ---------------------------------------------------------------------------
# Combine region and product, sum revenue for each pair, and return the top earner.
query_5 = """
SELECT
    region,
    product,
    ROUND(SUM(amount), 2) AS total_revenue
FROM sales
GROUP BY region, product
ORDER BY total_revenue DESC
LIMIT 1
"""

run_query(
    "Query 5: Top Region + Product Combination",
    "Find which region and product pairing brings in the highest combined revenue.",
    query_5,
)

connection.close()
print("=" * 70)
print("Done. Database connection closed.")
