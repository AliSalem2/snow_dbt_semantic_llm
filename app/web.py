"""Web demo and remote MCP endpoint in one FastAPI service.

  GET  /             chat page
  GET  /api/metrics  the governed metric catalogue
  POST /api/chat     one question -> Claude + tools -> answer, tool steps, SQL
  POST /mcp          the same tools for MCP clients (streamable HTTP)

Run locally:  DBT_TARGET=serve uvicorn app.web:app --reload
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app import semantic
from app.mcp_server import INSTRUCTIONS, server

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
MAX_TOKENS = 1500
MAX_TOOL_ROUNDS = 8
MAX_QUESTION_CHARS = 500
MAX_HISTORY_TURNS = 6
QUESTIONS_PER_HOUR_PER_IP = int(os.getenv("QUESTIONS_PER_HOUR_PER_IP", "15"))
QUESTIONS_PER_DAY_TOTAL = int(os.getenv("QUESTIONS_PER_DAY_TOTAL", "300"))

STATIC_DIR = Path(__file__).parent / "static"
# When set, /mcp requires "Authorization: Bearer <MCP_TOKEN>". Unset means open,
# which is fine locally but must never be the case for a public deployment.
MCP_TOKEN = os.getenv("MCP_TOKEN", "")

SYSTEM_PROMPT = INSTRUCTIONS + """
You are answering visitors of a public demo page, often recruiters.
Answer in short Markdown: lead with the answer, then a small table if useful.
Format BRL amounts with thousands separators. Name the metric you used in
plain words, and mention any definition that changes the meaning (for example
that revenue includes freight). Only answer questions about this dataset.
"""

TOOL_FUNCTIONS = {
    "list_metrics": semantic.list_metrics,
    "get_dimensions": semantic.get_dimensions,
    "query_metrics": semantic.query_metrics,
}

# --- MCP over HTTP -----------------------------------------------------------
# Stateless so any Cloud Run instance can serve any request. Host checks are
# off because Cloud Run terminates TLS and rewrites hosts in front of us.
mcp_app = server.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

@contextlib.asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Run the MCP session manager, and load the semantic layer in the background.

    Loading parses the dbt project and opens the Snowflake connection, which
    takes a few seconds. Doing it at startup means the first visitor does not
    pay for it.
    """
    warmup = asyncio.create_task(_warm_up())
    async with mcp_app.router.lifespan_context(fastapi_app):
        yield
    warmup.cancel()


async def _warm_up() -> None:
    try:
        await run_in_threadpool(semantic.list_metrics)
        logging.info("Semantic layer ready")
    except Exception as exc:  # the app still starts; queries will report the error
        logging.error("Warm-up failed: %s", exc)


app = FastAPI(title="Olist metrics demo", lifespan=lifespan)
client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY


@app.middleware("http")
async def protect_mcp(request: Request, call_next):
    """The chat page is public; the raw MCP endpoint is not."""
    if request.url.path.startswith("/mcp") and MCP_TOKEN:
        if request.headers.get("authorization", "") != f"Bearer {MCP_TOKEN}":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)


# --- Simple in-memory limits (run Cloud Run with max-instances=1) -------------
_ip_hits: dict[str, deque[float]] = defaultdict(deque)
_day = {"date": time.strftime("%Y-%m-%d"), "count": 0}


def _check_limits(ip: str) -> int:
    """Raise 429 when a limit is hit; return questions left for this visitor."""
    now = time.time()
    today = time.strftime("%Y-%m-%d")
    if _day["date"] != today:
        _day.update(date=today, count=0)
    if _day["count"] >= QUESTIONS_PER_DAY_TOTAL:
        raise HTTPException(429, "The demo reached its daily question limit. Try again tomorrow.")

    hits = _ip_hits[ip]
    while hits and now - hits[0] > 3600:
        hits.popleft()
    if len(hits) >= QUESTIONS_PER_HOUR_PER_IP:
        raise HTTPException(429, "You reached the hourly question limit. Try again later.")

    hits.append(now)
    _day["count"] += 1
    return QUESTIONS_PER_HOUR_PER_IP - len(hits)


# --- API ---------------------------------------------------------------------
class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[Turn] = []


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/metrics")
async def metrics() -> list[dict[str, str]]:
    return await run_in_threadpool(semantic.list_metrics)


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> dict[str, Any]:
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Type a question first.")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(400, f"Keep questions under {MAX_QUESTION_CHARS} characters.")

    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?")
    remaining = _check_limits(ip.split(",")[0].strip())

    history = body.history[-MAX_HISTORY_TURNS:]
    messages: list[dict[str, Any]] = [{"role": t.role, "content": t.content} for t in history]
    messages.append({"role": "user", "content": question})

    answer, steps, usage = await _run_agent(messages)
    return {"answer": answer, "steps": steps, "usage": usage, "remaining": remaining}


async def _tool_definitions() -> list[dict[str, Any]]:
    """Reuse the MCP server's tool schemas, so web and MCP stay identical."""
    tools = await server.list_tools()
    return [
        {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
        for t in tools
    ]


async def _run_agent(messages: list[dict[str, Any]]) -> tuple[str, list[dict], dict]:
    tools = await _tool_definitions()
    steps: list[dict[str, Any]] = []
    usage = {"input_tokens": 0, "output_tokens": 0}

    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )
        usage["input_tokens"] += response.usage.input_tokens
        usage["output_tokens"] += response.usage.output_tokens

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            return text, steps, usage

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            output = await _call_tool(block.name, block.input)
            steps.append(_describe_step(block.name, block.input, output))
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(output, default=str),
                    "is_error": isinstance(output, dict) and "error" in output,
                }
            )
        messages.append({"role": "user", "content": results})

    return "I could not finish this question within the step limit. Try asking it more narrowly.", steps, usage


async def _call_tool(name: str, args: dict[str, Any]) -> Any:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": f"Unknown tool {name!r}"}
    try:
        return await run_in_threadpool(func, **args)
    except TypeError as exc:  # wrong arguments from the model
        return {"error": f"Invalid arguments for {name}: {exc}"}


def _describe_step(name: str, args: dict[str, Any], output: Any) -> dict[str, Any]:
    """What the page shows under each answer."""
    step: dict[str, Any] = {"tool": name, "input": args}
    if isinstance(output, dict):
        if "error" in output:
            step["error"] = output["error"][:300]
        if "sql" in output:
            step["sql"] = output["sql"]
            step["row_count"] = output.get("row_count")
    return step


# Mounted last so the routes above take precedence.
app.mount("/", mcp_app)
