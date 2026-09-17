"""Tool layer: a thin, safe wrapper around the MetricFlow engine.

Both the MCP server and the web chat call these three functions, so every
client gets the same metrics, the same validation and the same limits.
The LLM never writes SQL: it names metrics and dimensions, and MetricFlow
compiles the query from the governed definitions in the dbt project.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import decimal
import os
import sys
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from dbt.cli.main import dbtRunner
from dbt_metricflow.cli.cli_configuration import CLIConfiguration
from metricflow.engine.metricflow_engine import MetricFlowEngine, MetricFlowQueryRequest

REPO_ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = Path(os.getenv("DBT_PROJECT_DIR", REPO_ROOT / "dbt"))
PROFILES_DIR = Path(os.getenv("DBT_PROFILES_DIR", DBT_DIR))
TARGET = os.getenv("DBT_TARGET", "dev")

MAX_ROWS = int(os.getenv("MAX_ROWS", "200"))
DEFAULT_LIMIT = 50
TIME_GRAINS = ["day", "week", "month", "quarter", "year"]

# The engine is not documented as thread-safe; web requests run in a thread pool.
_lock = threading.Lock()


def _parse_project() -> None:
    """Re-parse the dbt project for TARGET.

    MetricFlow reads table locations from the last `dbt parse`. Parsing here
    guarantees the server queries the schemas of its own target (e.g. MARTS
    for `serve`), not whatever target was parsed last.
    dbt output goes to stderr so it cannot corrupt the MCP stdio stream.
    """
    with contextlib.redirect_stdout(sys.stderr):
        result = dbtRunner().invoke(
            [
                "parse",
                "--quiet",
                "--project-dir", str(DBT_DIR),
                "--profiles-dir", str(PROFILES_DIR),
                "--target", TARGET,
            ]
        )
    if not result.success:
        raise RuntimeError(f"dbt parse failed for target {TARGET!r}: {result.exception}")


@lru_cache(maxsize=1)
def _engine() -> MetricFlowEngine:
    """Parse the project, load the semantic manifest and connect, once."""
    _parse_project()
    cfg = CLIConfiguration()
    cfg.setup(
        dbt_profiles_path=PROFILES_DIR,
        dbt_project_path=DBT_DIR,
        configure_file_logging=False,
    )
    return cfg.mf


def _to_json(value: Any) -> Any:
    """Convert warehouse values into JSON-friendly types."""
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, float):
        return round(value, 4)
    return value


def list_metrics() -> list[dict[str, str]]:
    """Every governed metric with its type and business description."""
    with _lock:
        metrics = _engine().list_metrics(include_dimensions=False)
    return sorted(
        (
            {
                "name": m.name,
                "type": str(m.type.value if hasattr(m.type, "value") else m.type),
                "description": (m.description or "").strip(),
            }
            for m in metrics
        ),
        key=lambda m: m["name"],
    )


def get_dimensions(metrics: list[str]) -> dict[str, Any]:
    """Dimensions that can be used to group or filter ALL the given metrics."""
    try:
        with _lock:
            dims = _engine().simple_dimensions_for_metrics(list(metrics))
    except Exception as exc:  # unknown metric names etc.
        return {"error": _short_error(exc)}
    names = sorted({d.granularity_free_dunder_name for d in dims})
    return {
        "dimensions": names,
        "time": {
            "dimension": "metric_time",
            "grains": TIME_GRAINS,
            "usage": "group by metric_time__<grain>, e.g. metric_time__month",
        },
    }


def query_metrics(
    metrics: list[str],
    group_by: list[str] | None = None,
    where: list[str] | None = None,
    order_by: list[str] | None = None,
    limit: int | None = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Compute metrics and return rows plus the SQL MetricFlow generated.

    where:    filters in MetricFlow syntax, e.g.
              "{{ Dimension('customer__home_state') }} = 'SP'"
              "{{ TimeDimension('metric_time', 'day') }} >= '2018-01-01'"
    order_by: metric or dimension names, prefix with '-' for descending.
    """
    limit = min(int(limit or DEFAULT_LIMIT), MAX_ROWS)
    request = MetricFlowQueryRequest.create(
        metric_names=list(metrics),
        group_by_names=list(group_by or []),
        where_constraints=list(where or []),
        order_by_names=list(order_by or []),
        limit=limit,
    )
    try:
        with _lock:
            result = _engine().query(request)
    except Exception as exc:
        return {"error": _short_error(exc)}

    table = result.result_df
    rows = [[_to_json(v) for v in row] for row in table.rows] if table else []
    return {
        # Snowflake returns upper-case names; normalise for every client.
        "columns": [c.lower() for c in table.column_names] if table else [],
        "rows": rows,
        "row_count": len(rows),
        # True when the row cap was reached, so more rows may exist.
        "hit_limit": len(rows) >= limit,
        "sql": _clean_sql(result.sql),
    }


def _clean_sql(sql: str) -> str:
    """Drop MetricFlow's planning comments so the SQL reads cleanly in the demo."""
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--")).strip()


def _short_error(exc: Exception, max_chars: int = 2000) -> str:
    """Keep MetricFlow's message (it lists valid suggestions) but cap its size."""
    return f"{type(exc).__name__}: {str(exc)[:max_chars]}"


if __name__ == "__main__":
    # Smoke test:  python -m app.semantic
    import json

    print(f"{len(list_metrics())} metrics")
    print(json.dumps(get_dimensions(["revenue"]), indent=2))
    result = query_metrics(
        ["revenue", "orders"],
        group_by=["customer__home_state"],
        order_by=["-revenue"],
        limit=3,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "sql"}, indent=2))
    print(query_metrics(["profit"])["error"][:300])
