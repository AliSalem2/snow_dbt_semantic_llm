"""MCP server exposing the governed Olist metrics.

Run over stdio (Claude Code, Claude Desktop):   python -m app.mcp_server
The web app mounts the same server over HTTP at /mcp.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Allow `python app/mcp_server.py` as well as `python -m app.mcp_server`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

from app import semantic  # noqa: E402

INSTRUCTIONS = """\
Governed metrics for the Olist Brazilian e-commerce dataset (orders from
Sep 2016 to Oct 2018; 2016 and 2018 are partial years). Amounts are in BRL.

Workflow:
1. list_metrics to find the metric that matches the question. Read the
   descriptions: e.g. revenue includes freight, product_revenue does not.
2. get_dimensions for the chosen metrics to see valid group_by and filter names.
3. query_metrics. Never guess names; if a call returns an error, read the
   suggestions in it and retry.

For shares or percentages, query the total separately (the same metric
without group_by) instead of summing a limited result. If no metric fits (for example profit or costs, which the data does not
contain), say so plainly instead of approximating with another metric.
States are Brazilian state codes (SP = Sao Paulo, RJ = Rio de Janeiro, ...).

For region or state questions about order-level metrics (revenue, orders,
deliveries, reviews), group by olist_order__customer_state, the state where
each order was placed. Use customer__home_state only for customer metrics
(new_customers, repeat rates) or when the user asks about customers' home state.
"""

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

server = MCPServer(name="olist-metrics", instructions=INSTRUCTIONS)


@server.tool(annotations=READ_ONLY)
def list_metrics() -> list[dict[str, str]]:
    """List every governed metric with its type and business definition.

    Call this first to choose the metric that answers the question.
    """
    return semantic.list_metrics()


@server.tool(annotations=READ_ONLY)
def get_dimensions(metrics: list[str]) -> dict[str, Any]:
    """List the dimensions that can group or filter ALL of the given metrics.

    Args:
        metrics: metric names from list_metrics, e.g. ["revenue", "orders"].
    """
    return semantic.get_dimensions(metrics)


@server.tool(annotations=READ_ONLY)
def query_metrics(
    metrics: list[str],
    group_by: list[str] | None = None,
    where: list[str] | None = None,
    order_by: list[str] | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Compute metrics from the semantic layer. Returns rows and the generated SQL.

    Args:
        metrics: metric names, e.g. ["revenue"].
        group_by: dimension names from get_dimensions, e.g. ["customer__home_state"].
            For time use metric_time__<grain>: day, week, month, quarter or year.
        where: filters in MetricFlow syntax, e.g.
            "{{ Dimension('customer__home_state') }} = 'SP'" or
            "{{ TimeDimension('metric_time', 'day') }} >= '2018-01-01'".
        order_by: metric or dimension names; prefix with "-" for descending.
        limit: maximum rows to return (capped at 200).
    """
    return semantic.query_metrics(metrics, group_by, where, order_by, limit)


if __name__ == "__main__":
    server.run(transport="stdio")
