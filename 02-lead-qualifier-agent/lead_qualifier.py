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

INPUT_CSV = "leads.csv"
OUTPUT_CSV = "qualified_leads.csv"
DELAY_SECONDS = 1
MODEL = "claude-sonnet-4-20250514"

PROMPT_TEMPLATE = """You are a lead qualification expert for an AI automation freelancer based in India. Score this company as a potential client for AI automation services.

Company: {company_name}
Industry: {industry}
Size: {size}

Respond in exactly this JSON format:
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
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    if not message.content or not message.content[0].text:
        raise ValueError("Empty response from Claude")

    return parse_claude_response(message.content[0].text)


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    input_path = base_dir / INPUT_CSV
    output_path = base_dir / OUTPUT_CSV

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
    total = len(df)

    for index, row in df.iterrows():
        company_name = str(row["company_name"]).strip()
        industry = str(row["industry"]).strip()
        size = str(row["size"]).strip()
        position = int(index) + 1

        print(f"[{position}/{total}] Qualifying: {company_name}...")

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
            print(f"  -> Score: {parsed['score']} | {parsed['reason']}")
        except Exception as exc:
            result_row["reason"] = f"Error: {exc}"
            print(f"  -> Failed: {exc}", file=sys.stderr)

        results.append(result_row)

        if position < total:
            time.sleep(DELAY_SECONDS)

    try:
        out_df = pd.DataFrame(results)
        out_df.to_csv(output_path, index=False)
        print(f"\nDone. Wrote {len(out_df)} rows to {output_path}")
    except Exception as exc:
        print(f"Error writing output CSV: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
