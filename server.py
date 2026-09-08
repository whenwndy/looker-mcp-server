import json
import os
from pathlib import Path
from typing import Optional
from fastmcp import FastMCP
from pydantic import Field

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

_DATA_PATH = Path(__file__).parent / "data" / "looker.json"
_db: dict = json.loads(_DATA_PATH.read_text())


def _match(record: dict, field: str, value: str) -> bool:
    """Case-insensitive substring match on a field."""
    return value.lower() in str(record.get(field, "")).lower()


def _search_fields(record: dict, fields: list[str], value: str) -> bool:
    """Case-insensitive substring match across multiple fields (any match wins)."""
    v = value.lower()
    return any(v in str(record.get(f, "")).lower() for f in fields)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="looker-mock",
    version="1.0.0",
    instructions=(
        "Mock Looker BI platform for Quince CX and commerce analytics. "
        "Use get_looks to find pre-built CX reports, run_look to execute them, "
        "or query() to run ad-hoc analysis. "
        "Best explores for CX: support_tickets, customer_satisfaction, agent_performance."
    ),
)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@mcp.tool()
def get_models(
    id: Optional[str] = Field(default=None, description="Filter by model ID, e.g. quince_cx"),
    name: Optional[str] = Field(default=None, description="Filter by model name (partial match)"),
) -> list[dict]:
    """List LookML models. Optionally filter by id or name."""
    results = _db["models"]
    if id:
        results = [r for r in results if r["id"].lower() == id.lower()]
    if name:
        results = [r for r in results if _match(r, "name", name)]
    return results


# ---------------------------------------------------------------------------
# Explores
# ---------------------------------------------------------------------------

@mcp.tool()
def get_explores(
    model_id: Optional[str] = Field(default=None, description="Filter by model ID, e.g. quince_cx"),
    model_name: Optional[str] = Field(default=None, description="Filter by model name (exact, case-insensitive)"),
    name: Optional[str] = Field(default=None, description="Filter by explore name (partial match), e.g. support_tickets"),
    search: Optional[str] = Field(default=None, description="Partial-match search across label and description"),
) -> list[dict]:
    """List explores across all models. Filter by model, name, or keyword search."""
    results = _db["explores"]
    if model_id:
        results = [r for r in results if r["model_id"].lower() == model_id.lower()]
    if model_name:
        results = [r for r in results if r["model_name"].lower() == model_name.lower()]
    if name:
        results = [r for r in results if _match(r, "name", name)]
    if search:
        results = [r for r in results if _search_fields(r, ["label", "description"], search)]
    return results


# ---------------------------------------------------------------------------
# Looks
# ---------------------------------------------------------------------------

@mcp.tool()
def get_looks(
    id: Optional[str] = Field(default=None, description="Filter by look ID, e.g. look_001"),
    title: Optional[str] = Field(default=None, description="Filter by look title (partial match)"),
    model: Optional[str] = Field(default=None, description="Filter by model name, e.g. quince_cx"),
    explore: Optional[str] = Field(default=None, description="Filter by explore name, e.g. support_tickets"),
    folder: Optional[str] = Field(default=None, description="Filter by folder name (partial match), e.g. CX Operations"),
    search: Optional[str] = Field(default=None, description="Partial-match search across title and description"),
) -> list[dict]:
    """Find pre-built CX reports and dashboards. Search for 'urgent', 'ticket', 'CSAT', or 'escalation' to find CX-relevant looks."""
    results = _db["looks"]
    if id:
        results = [r for r in results if r["id"].lower() == id.lower()]
    if title:
        results = [r for r in results if _match(r, "title", title)]
    if model:
        results = [r for r in results if r["model"].lower() == model.lower()]
    if explore:
        results = [r for r in results if r["explore"].lower() == explore.lower()]
    if folder:
        results = [r for r in results if _match(r, "folder", folder)]
    if search:
        results = [r for r in results if _search_fields(r, ["title", "description"], search)]
    return results


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------

@mcp.tool()
def get_dashboards(
    id: Optional[str] = Field(default=None, description="Filter by dashboard ID, e.g. dash_001"),
    title: Optional[str] = Field(default=None, description="Filter by dashboard title (partial match)"),
    folder: Optional[str] = Field(default=None, description="Filter by folder name (partial match)"),
    search: Optional[str] = Field(default=None, description="Partial-match search across title and description"),
) -> list[dict]:
    """List saved dashboards. Optionally filter by id, title, folder, or keyword search."""
    results = _db["dashboards"]
    if id:
        results = [r for r in results if r["id"].lower() == id.lower()]
    if title:
        results = [r for r in results if _match(r, "title", title)]
    if folder:
        results = [r for r in results if _match(r, "folder", folder)]
    if search:
        results = [r for r in results if _search_fields(r, ["title", "description"], search)]
    return results


# ---------------------------------------------------------------------------
# Run Look
# ---------------------------------------------------------------------------

@mcp.tool()
def run_look(
    id: str = Field(description="Look ID to execute, e.g. look_001"),
) -> dict:
    """Execute a saved Look by ID. Returns the look metadata plus its query result data if available."""
    looks = [r for r in _db["looks"] if r["id"].lower() == id.lower()]
    if not looks:
        return {"error": f"Look '{id}' not found."}
    look = looks[0]

    # Find a matching query_result by title similarity
    look_title_lower = look["title"].lower()
    matched_qr = None
    for qr in _db["query_results"]:
        qr_words = set(qr["title"].lower().split())
        look_words = set(look_title_lower.split())
        # Match if model+explore align or titles share significant keywords
        if qr["model"] == look["model"] and qr["explore"] == look["explore"]:
            overlap = qr_words & look_words
            non_stopwords = {w for w in overlap if w not in {"by", "the", "a", "an", "of", "in", "and", "or", "vs", "last", "this"}}
            if len(non_stopwords) >= 2:
                matched_qr = qr
                break

    return {
        "look": look,
        "query_result": matched_qr,
    }


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

@mcp.tool()
def query(
    model: str = Field(description="LookML model name, e.g. quince_cx"),
    explore: str = Field(description="Explore name, e.g. support_tickets"),
    dimensions: Optional[str] = Field(default=None, description="Comma-separated dimension names, e.g. support_tickets.priority,support_tickets.status"),
    measures: Optional[str] = Field(default=None, description="Comma-separated measure names, e.g. support_tickets.count"),
    filters_json: Optional[str] = Field(default=None, description="Optional JSON string of filters, e.g. {\"support_tickets.status\": \"Open\"}"),
    limit: int = Field(default=500, description="Maximum number of rows to return (default 500)"),
) -> dict:
    """Run an ad-hoc Looker query. Finds the best matching pre-built result or returns a mock result."""
    dim_list = [d.strip() for d in dimensions.split(",")] if dimensions else []
    meas_list = [m.strip() for m in measures.split(",")] if measures else []

    # Parse filters
    filters = {}
    if filters_json:
        try:
            filters = json.loads(filters_json)
        except json.JSONDecodeError:
            return {"error": "filters_json is not valid JSON.", "model": model, "explore": explore}

    # Find best matching pre-built query result (model + explore match, then dimension overlap)
    best_match = None
    best_score = 0
    for qr in _db["query_results"]:
        if qr["model"].lower() != model.lower() or qr["explore"].lower() != explore.lower():
            continue
        # Score by dimension overlap
        qr_dims = set(qr["dimensions"])
        req_dims = set(dim_list)
        # Also try suffix matching (e.g. "priority" matches "support_tickets.priority")
        def suffix_in(full_set, short):
            return any(short == f or f.endswith("." + short) for f in full_set)

        overlap = sum(1 for d in req_dims if suffix_in(qr_dims, d) or suffix_in(req_dims, d.split(".")[-1]))
        score = overlap + (1 if qr["model"] == model else 0) + (1 if qr["explore"] == explore else 0)
        if score > best_score:
            best_score = score
            best_match = qr

    if best_match:
        rows = best_match["result_rows"][:limit]
        return {
            "model": model,
            "explore": explore,
            "dimensions": dim_list,
            "measures": meas_list,
            "filters": filters,
            "source": "pre_built_result",
            "matched_query": best_match["title"],
            "row_count": len(rows),
            "result_rows": rows,
            "ran_at": best_match["ran_at"],
        }

    # No match — return mock empty result with schema hint
    return {
        "model": model,
        "explore": explore,
        "dimensions": dim_list,
        "measures": meas_list,
        "filters": filters,
        "source": "mock_empty",
        "row_count": 0,
        "result_rows": [],
        "note": (
            "No pre-built result matched this exact query. "
            "Try one of the available explores: support_tickets, customer_satisfaction, "
            "agent_performance, orders, returns, inventory, campaigns, customer_segments."
        ),
    }


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

@mcp.tool()
def get_connections(
    id: Optional[str] = Field(default=None, description="Filter by connection ID, e.g. quince_warehouse"),
    name: Optional[str] = Field(default=None, description="Filter by connection name (partial match)"),
) -> list[dict]:
    """List database connections configured in Looker. Optionally filter by id or name."""
    results = _db["connections"]
    if id:
        results = [r for r in results if r["id"].lower() == id.lower()]
    if name:
        results = [r for r in results if _match(r, "name", name)]
    return results


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@mcp.tool()
def get_projects(
    id: Optional[str] = Field(default=None, description="Filter by project ID, e.g. quince_lookml"),
    name: Optional[str] = Field(default=None, description="Filter by project name (partial match)"),
) -> list[dict]:
    """List LookML projects. Optionally filter by id or name."""
    results = _db["projects"]
    if id:
        results = [r for r in results if r["id"].lower() == id.lower()]
    if name:
        results = [r for r in results if _match(r, "name", name)]
    return results


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@mcp.tool()
def health_pulse() -> dict:
    """Return the current Looker instance health status, including system checks, query performance, and active user counts."""
    return _db["health_status"]


@mcp.tool()
def health_analyze(
    explore_name: str = Field(description="Explore name to analyze, e.g. support_tickets"),
) -> dict:
    """Return usage statistics and health analysis for a specific explore."""
    explores = [e for e in _db["explores"] if e["name"].lower() == explore_name.lower()]
    if not explores:
        return {"error": f"Explore '{explore_name}' not found."}
    explore = explores[0]

    # Mock usage analysis scoped realistically to the explore
    usage = {
        "support_tickets":       {"query_count_30d": 3842, "avg_query_time_ms": 280,  "slow_queries_count": 12, "last_used_at": "2026-09-08T08:03:00Z"},
        "customer_satisfaction": {"query_count_30d": 2107, "avg_query_time_ms": 195,  "slow_queries_count": 4,  "last_used_at": "2026-09-08T07:45:00Z"},
        "agent_performance":     {"query_count_30d": 1654, "avg_query_time_ms": 230,  "slow_queries_count": 7,  "last_used_at": "2026-09-08T08:00:00Z"},
        "orders":                {"query_count_30d": 4211, "avg_query_time_ms": 415,  "slow_queries_count": 29, "last_used_at": "2026-09-08T07:58:00Z"},
        "returns":               {"query_count_30d": 2890, "avg_query_time_ms": 350,  "slow_queries_count": 18, "last_used_at": "2026-09-08T06:30:00Z"},
        "inventory":             {"query_count_30d": 1320, "avg_query_time_ms": 188,  "slow_queries_count": 3,  "last_used_at": "2026-09-08T05:00:00Z"},
        "campaigns":             {"query_count_30d": 987,  "avg_query_time_ms": 510,  "slow_queries_count": 22, "last_used_at": "2026-09-07T18:00:00Z"},
        "customer_segments":     {"query_count_30d": 743,  "avg_query_time_ms": 620,  "slow_queries_count": 31, "last_used_at": "2026-09-07T15:00:00Z"},
    }.get(explore["name"], {"query_count_30d": 0, "avg_query_time_ms": 0, "slow_queries_count": 0, "last_used_at": None})

    return {
        "explore": explore,
        "usage_analysis": usage,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
