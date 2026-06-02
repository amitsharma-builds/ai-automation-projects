import ast
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv
from tqdm import tqdm

INPUT_CSV = "leads.csv"
OUTPUT_CSV = "qualified_leads.csv"
SUMMARY_FILE = "leads_summary.txt"
DELAY_SECONDS = 1
MODEL = "claude-sonnet-4-20250514"

PROMPT_TEMPLATE = """You are a lead qualification expert for an AI automation freelancer based in India. Score this company as a potential client for AI automation services.

Company: {company_name}
Industry: {industry}
Size: {size}

Think step by step before you score:

Step 1 — Pain points: What operational challenges, inefficiencies, or scaling pains is this company likely facing given their industry and size?

Step 2 — AI automation fit: How much would they benefit from AI automation? Consider transaction volume, manual workflows, tech maturity, budget signals, and realistic automation opportunities.

Step 3 — Final judgment: Based on steps 1 and 2, assign a lead score from 1 (poor fit) to 10 (excellent fit) and explain in one sentence.

Respond in exactly this JSON format (your final answer must be only this JSON object):
{{
  'score': <number 1-10>,
  'reason': '<one sentence why>',
  'best_use_case': '<one specific AI automation use case for them>'
}}"""


def load_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found. Add it to your .env file.")
    return api_key


def extract_json_text(text: str) -> str:
    """Pull JSON object from plain text or markdown code fences."""
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def parse_claude_response(text: str) -> dict:
    """Parse JSON from Claude; tolerate single-quoted dicts from the prompt format."""
    raw = extract_json_text(text)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            data = ast.literal_eval(raw)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"Could not parse response as JSON: {raw!r}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got: {type(data).__name__}")

    required = ("score", "reason", "best_use_case")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Missing keys in response: {missing}")

    score = int(data["score"])
    if not 1 <= score <= 10:
        raise ValueError(f"Score must be 1-10, got: {score}")

    return {
        "score": score,
        "reason": str(data["reason"]).strip(),
        "best_use_case": str(data["best_use_case"]).strip(),
    }


def qualify_company(
    client: Anthropic,
    company_name: str,
    industry: str,
    size: str,
) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        company_name=company_name,
        industry=industry,
        size=size,
    )

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    if not message.content or not message.content[0].text:
        raise ValueError("Empty response from Claude")

    return parse_claude_response(message.content[0].text)


def build_summary(df: pd.DataFrame) -> str:
    """Build a text summary from qualified leads with valid scores."""
    valid = df.dropna(subset=["score"]).copy()
    valid["score"] = valid["score"].astype(int)

    lines = [
        "=" * 50,
        "LEAD QUALIFICATION SUMMARY",
        "=" * 50,
        "",
        f"Total leads processed: {len(df)}",
        f"Successfully scored: {len(valid)}",
        f"Failed or skipped: {len(df) - len(valid)}",
        "",
    ]

    if valid.empty:
        lines.append("No valid scores to summarize.")
        return "\n".join(lines)

    avg_score = valid["score"].mean()
    lines.append(f"Average score: {avg_score:.2f}")
    lines.append("")

    top3 = valid.nlargest(3, "score")
    lines.append("Top 3 leads by score:")
    lines.append("-" * 50)
    for rank, row in enumerate(top3.itertuples(index=False), start=1):
        lines.append(
            f"  {rank}. {row.company_name} ({row.industry}) — "
            f"Score: {row.score}"
        )
        lines.append(f"     Reason: {row.reason}")
    lines.append("")

    industry_avg = valid.groupby("industry", as_index=False)["score"].mean()
    industry_avg = industry_avg.sort_values("score", ascending=False)
    best_row = industry_avg.iloc[0]
    lines.append("Industry rankings (average score):")
    lines.append("-" * 50)
    for row in industry_avg.itertuples(index=False):
        lines.append(f"  {row.industry}: {row.score:.2f}")
    lines.append("")
    lines.append(
        f"Highest-scoring industry on average: {best_row.industry} "
        f"({best_row.score:.2f})"
    )
    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)


def save_summary(summary: str, output_path: Path) -> None:
    output_path.write_text(summary, encoding="utf-8")


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    input_path = base_dir / INPUT_CSV
    output_path = base_dir / OUTPUT_CSV
    summary_path = base_dir / SUMMARY_FILE

    if not input_path.exists():
        print(f"Error: {input_path} not found.", file=sys.stderr)
        sys.exit(1)

    try:
        api_key = load_api_key()
        client = Anthropic(api_key=api_key)
        df = pd.read_csv(input_path)
    except Exception as exc:
        print(f"Startup error: {exc}", file=sys.stderr)
        sys.exit(1)

    required_columns = {"company_name", "industry", "size"}
    missing_cols = required_columns - set(df.columns)
    if missing_cols:
        print(
            f"Error: {INPUT_CSV} missing columns: {sorted(missing_cols)}",
            file=sys.stderr,
        )
        sys.exit(1)

    results = []
    rows = list(df.iterrows())

    for index, (_, row) in enumerate(
        tqdm(rows, desc="Qualifying leads", unit="lead")
    ):
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
            tqdm.write(
                f"  {company_name}: score {parsed['score']} — {parsed['reason']}"
            )
        except Exception as exc:
            result_row["reason"] = f"Error: {exc}"
            tqdm.write(f"  {company_name}: failed — {exc}")

        results.append(result_row)

        if index < len(rows) - 1:
            time.sleep(DELAY_SECONDS)

    try:
        out_df = pd.DataFrame(results)
        out_df.to_csv(output_path, index=False)
        tqdm.write(f"\nWrote {len(out_df)} rows to {output_path}")
    except Exception as exc:
        print(f"Error writing output CSV: {exc}", file=sys.stderr)
        sys.exit(1)

    summary = build_summary(out_df)
    try:
        save_summary(summary, summary_path)
        tqdm.write(f"Wrote summary to {summary_path}")
    except Exception as exc:
        print(f"Error writing summary file: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n" + summary)


if __name__ == "__main__":
    main()
