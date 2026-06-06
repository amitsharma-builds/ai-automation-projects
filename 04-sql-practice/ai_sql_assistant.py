"""
AI SQL assistant: convert plain-English questions to SQL via Claude and run against sales.db.
"""

import os
import re
import sqlite3

import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

DB_NAME = "sales.db"

DATABASE_SCHEMA = """Table: sales
Columns: id, date, product, region, amount, units, segment"""


def build_sql_prompt(question: str) -> str:
    """Build the prompt sent to Claude for SQL generation."""
    return f"""You are a SQL expert. Convert this question to a SQLite SQL query.

Database schema:
{DATABASE_SCHEMA}

Question: {question}

Return ONLY the SQL query, nothing else.
No explanation, no markdown, just the raw SQL."""


def clean_sql_response(raw_sql: str) -> str:
    """Strip markdown fences if Claude wraps the query anyway."""
    sql = raw_sql.strip()
    if sql.startswith("```"):
        sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*```$", "", sql)
    return sql.strip()


def generate_sql(question: str, client: Anthropic) -> str:
    """Send a plain-English question to Claude and return the generated SQL."""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": build_sql_prompt(question)}],
    )
    return clean_sql_response(response.content[0].text)


def ask_database(
    question: str,
    connection: sqlite3.Connection,
    client: Anthropic,
) -> tuple[str, pd.DataFrame]:
    """
    Take a plain-English question, convert it to SQL via Claude,
    run the query against the database, and return the SQL and results.
    """
    sql = generate_sql(question, client)
    results = pd.read_sql_query(sql, connection)
    return sql, results


def main() -> None:
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found. Add it to your .env file.")

    client = Anthropic(api_key=api_key)
    connection = sqlite3.connect(DB_NAME)

    test_questions = [
        "Which product made the most money?",
        "Show me all Enterprise deals above 50000",
        "What is the average deal size in the North region?",
    ]

    for question in test_questions:
        print("=" * 70)
        print(f"Question: {question}")

        sql, results = ask_database(question, connection, client)

        print(f"\nSQL Generated:\n{sql}")
        print(f"\nResults:\n{results.to_string(index=False)}\n")

    connection.close()


if __name__ == "__main__":
    main()
