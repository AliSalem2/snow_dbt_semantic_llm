"""Evaluate two ways of answering business questions.

  semantic : Claude uses the governed metrics (the same tools as the demo)
  sql      : Claude writes SQL directly against the marts tables

Both answer the same 20 questions. A third Claude call grades each answer
against hand-written gold SQL, so neither system is graded against itself.

Usage (repo root, .env loaded):
    DBT_TARGET=serve python -m eval.run_eval              # both modes
    DBT_TARGET=serve python -m eval.run_eval --mode sql   # one mode
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import yaml
from anthropic import AsyncAnthropic
from starlette.concurrency import run_in_threadpool

from app import semantic
from app.web import SYSTEM_PROMPT, _tool_definitions, _call_tool

EVAL_DIR = Path(__file__).parent
SCHEMA = os.getenv("EVAL_SCHEMA", "ANALYTICS.MARTS")
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
MAX_ROUNDS = 8
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|create|alter|merge|truncate|grant|revoke|copy)\b", re.I
)

client = AsyncAnthropic()

SQL_SYSTEM = """\
You answer business questions about a Brazilian e-commerce marketplace by
writing SQL against a Snowflake warehouse. Orders run from Sep 2016 to Oct 2018
and amounts are in BRL.

Use the run_sql tool. Read-only queries only. The schema is {schema}:

{ddl}

Answer in short Markdown. If the data cannot answer the question, say so
plainly instead of approximating.
"""

GRADER_SYSTEM = """\
You grade an analytics assistant's answer.

You get the question, the correct result (from hand-written SQL), and the
answer. Reply with JSON only: {"verdict": "pass" | "fail", "reason": "<15 words"}

Pass when the answer states the correct figures (within 1% for rounding) or the
correct ranking. Wording, extra commentary and formatting do not matter.
Fail when a headline number is wrong or missing, when the ranking is wrong, or
when the answer claims something the correct result contradicts.

For questions marked unanswerable there is no correct result: pass only if the
answer says the data cannot answer it, and does not invent a figure.
"""


# --- warehouse ---------------------------------------------------------------
def run_sql(sql: str) -> dict[str, Any]:
    """Read-only query for gold results and for the text-to-SQL baseline."""
    if FORBIDDEN_SQL.search(sql):
        return {"error": "Only read-only queries are allowed."}
    try:
        table = semantic.sql_client().query(sql)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:800]}"}
    rows = [[semantic._to_json(v) for v in row] for row in table.rows[:200]]
    return {"columns": [c.lower() for c in table.column_names], "rows": rows}


def load_ddl() -> str:
    """Column list of the marts tables, the context the baseline needs."""
    database, schema = SCHEMA.split(".")
    result = run_sql(
        f"""
        select table_name, column_name, data_type
        from {database}.information_schema.columns
        where table_schema = '{schema.upper()}'
        order by table_name, ordinal_position
        """
    )
    if "error" not in result and result["rows"]:
        tables: dict[str, list[str]] = {}
        for table, column, dtype in result["rows"]:
            tables.setdefault(table.lower(), []).append(f"{column.lower()} {dtype.lower()}")
        return "\n".join(f"{t}({', '.join(cols)})" for t, cols in tables.items())

    # Fallback for warehouses that expose information_schema differently:
    # read the column names straight off each table.
    lines = []
    for table in ("fct_orders", "fct_order_items", "dim_customer_profiles", "dim_products", "dim_sellers", "dim_customers"):
        probe = run_sql(f"select * from {SCHEMA}.{table} limit 0")
        if "error" not in probe:
            lines.append(f"{table}({', '.join(probe['columns'])})")
    return "\n".join(lines)


# --- the two systems ---------------------------------------------------------
async def answer_with_semantic_layer(question: str) -> dict[str, Any]:
    from app.web import _run_agent

    started = time.time()
    answer, steps, usage = await _run_agent([{"role": "user", "content": question}])
    return {
        "answer": answer,
        "tool_calls": len(steps),
        "seconds": round(time.time() - started, 1),
        "usage": usage,
    }


async def answer_with_sql(question: str, ddl: str) -> dict[str, Any]:
    tools = [
        {
            "name": "run_sql",
            "description": "Run a read-only SQL query and return the rows.",
            "input_schema": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        }
    ]
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    usage = {"input_tokens": 0, "output_tokens": 0}
    queries = 0
    started = time.time()

    for _ in range(MAX_ROUNDS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SQL_SYSTEM.format(schema=SCHEMA, ddl=ddl),
            tools=tools,
            messages=messages,
        )
        usage["input_tokens"] += response.usage.input_tokens
        usage["output_tokens"] += response.usage.output_tokens

        if response.stop_reason != "tool_use":
            answer = "".join(b.text for b in response.content if b.type == "text").strip()
            return {
                "answer": answer,
                "tool_calls": queries,
                "seconds": round(time.time() - started, 1),
                "usage": usage,
            }

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            queries += 1
            output = await run_in_threadpool(run_sql, block.input.get("sql", ""))
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(output, default=str)[:20000],
                    "is_error": "error" in output,
                }
            )
        messages.append({"role": "user", "content": results})

    return {
        "answer": "(gave up after the step limit)",
        "tool_calls": queries,
        "seconds": round(time.time() - started, 1),
        "usage": usage,
    }


# --- grading -----------------------------------------------------------------
async def grade(question: dict[str, Any], answer: str, gold: Any) -> dict[str, str]:
    payload = {
        "question": question["question"],
        "expect": question["expect"],
        "correct_result": gold,
        "answer": answer,
    }
    response = await client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=GRADER_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:  # rare empty completion: retry once before failing
        response = await client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=GRADER_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
    try:
        return json.loads(re.sub(r"^```(json)?|```$", "", text, flags=re.M).strip())
    except json.JSONDecodeError:
        return {"verdict": "fail", "reason": f"grader returned: {text[:60]}"}
# --- runner ------------------------------------------------------------------
async def main(modes: list[str]) -> None:
    questions = yaml.safe_load((EVAL_DIR / "questions.yaml").read_text())
    print(f"Loading the semantic layer and schema for {SCHEMA} ...")
    ddl = await run_in_threadpool(load_ddl)
    await _tool_definitions()  # fail fast if the MCP tools cannot be listed

    results = []
    for question in questions:
        gold = None
        if question["expect"] == "answerable":
            gold = await run_in_threadpool(run_sql, question["gold_sql"].format(schema=SCHEMA))

        row: dict[str, Any] = {"id": question["id"], "question": question["question"], "gold": gold}
        for mode in modes:
            run = (
                await answer_with_semantic_layer(question["question"])
                if mode == "semantic"
                else await answer_with_sql(question["question"], ddl)
            )
            verdict = await grade(question, run["answer"], gold)
            run.update(verdict)
            row[mode] = run
            print(f"{question['id']:>4} {mode:<8} {verdict['verdict']:<4} {verdict['reason'][:60]}")
        results.append(row)

    (EVAL_DIR / "results.json").write_text(json.dumps(results, indent=2, default=str))
    (EVAL_DIR / "results.md").write_text(summarise(results, modes))
    print("\n" + summarise(results, modes))


def summarise(results: list[dict[str, Any]], modes: list[str]) -> str:
    lines = ["# Evaluation results", "", f"{len(results)} business questions, graded against hand-written SQL.", ""]
    lines.append("| Mode | Correct | Accuracy | Avg tool calls | Avg seconds |")
    lines.append("|---|---|---|---|---|")
    for mode in modes:
        runs = [r[mode] for r in results if mode in r]
        passed = sum(1 for run in runs if run.get("verdict") == "pass")
        lines.append(
            f"| {'Semantic layer' if mode == 'semantic' else 'Raw text-to-SQL'} "
            f"| {passed}/{len(runs)} | {passed / len(runs):.0%} "
            f"| {sum(r['tool_calls'] for r in runs) / len(runs):.1f} "
            f"| {sum(r['seconds'] for r in runs) / len(runs):.1f} |"
        )

    lines += ["", "## Per question", "", "| # | Question | " + " | ".join(m for m in modes) + " |",
              "|---|---|" + "---|" * len(modes)]
    for r in results:
        marks = " | ".join("pass" if r.get(m, {}).get("verdict") == "pass" else "fail" for m in modes)
        lines.append(f"| {r['id']} | {r['question']} | {marks} |")

    failures = [
        f"- **{r['id']} ({mode})**: {r[mode]['reason']}"
        for r in results
        for mode in modes
        if r.get(mode, {}).get("verdict") != "pass"
    ]
    if failures:
        lines += ["", "## Failures", ""] + failures
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["semantic", "sql", "both"], default="both")
    args = parser.parse_args()
    asyncio.run(main(["semantic", "sql"] if args.mode == "both" else [args.mode]))
