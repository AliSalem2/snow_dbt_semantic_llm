"""Start the MCP server over stdio and call each tool once.

Usage (repo root, .env loaded):  DBT_TARGET=serve python scripts/mcp_smoke_test.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

REPO_ROOT = Path(__file__).resolve().parent.parent


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server"],
        cwd=str(REPO_ROOT),
        env=dict(os.environ),
    )
    async with Client(params) as client:
        tools = await client.list_tools()
        print("Tools:", [t.name for t in tools.tools])

        result = await client.call_tool("get_dimensions", {"metrics": ["new_customers"]})
        print("Dimensions for new_customers:", result.structured_content)

        result = await client.call_tool(
            "query_metrics",
            {
                "metrics": ["new_customers", "repeat_purchase_rate"],
                "group_by": ["customer__home_state"],
                "order_by": ["-new_customers"],
                "limit": 3,
            },
        )
        data = result.structured_content
        if "error" in data:
            print("Query failed:", data["error"][:500])
            return
        print("Rows:", json.dumps(data["rows"]))
        print("SQL:\n" + data["sql"])

        result = await client.call_tool("query_metrics", {"metrics": ["profit"]})
        print("Expected error:", result.structured_content["error"][:120])


if __name__ == "__main__":
    asyncio.run(main())
