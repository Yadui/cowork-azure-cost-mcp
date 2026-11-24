"""Azure Cost MCP server for Copilot Cowork.

Exposes four read-only tools over Streamable HTTP:
  get_costs      - actual/amortized cost for a scope, grouped by a dimension
  get_forecast   - forecast for the rest of the current month
  top_spenders   - top N resource groups / services month-to-date
  list_scopes    - the allow-listed scopes

Inbound: Entra ID bearer token (validated here; Cowork obtains it via OAuthPluginVault).
Outbound: the server's own identity (managed identity in Azure, az login locally)
          which needs Cost Management Reader on the scopes in ALLOWED_SCOPES.
"""
import os
from datetime import date, timedelta

import httpx
import jwt
from azure.identity.aio import DefaultAzureCredential
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

API_VERSION = os.getenv("COST_API_VERSION", "2026-06-01")
ARM = "https://management.azure.com"
TENANT_ID = os.environ["TENANT_ID"]
AUDIENCE = os.environ["API_AUDIENCE"]  # v2 tokens: the API app's client ID (GUID), not api://...
ALLOWED_SCOPES = [s.strip() for s in os.environ["ALLOWED_SCOPES"].split(",") if s.strip()]
DEFAULT_SCOPE = ALLOWED_SCOPES[0]

credential = DefaultAzureCredential()
jwks = jwt.PyJWKClient(f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys")

# The SDK's DNS-rebinding protection only allows localhost by default; allow-list the public host.
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost:*,127.0.0.1:*").split(",") if h.strip()]
mcp = FastMCP(
    "azure-cost",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=ALLOWED_HOSTS, allowed_origins=[]
    ),
)

# Cowork treats tools without annotations as destructive and asks for confirmation.
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)


# ---------- Cost Management helpers ----------

def _scope(scope: str | None) -> str:
    s = scope or DEFAULT_SCOPE
    if s not in ALLOWED_SCOPES:
        raise ValueError(f"Scope not allowed. Allowed: {', '.join(ALLOWED_SCOPES)}")
    return s


async def _post(scope: str, op: str, body: dict) -> dict:
    token = (await credential.get_token(f"{ARM}/.default")).token
    url = f"{ARM}{scope}/providers/Microsoft.CostManagement/{op}?api-version={API_VERSION}"
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 429:
            retry = r.headers.get("x-ms-ratelimit-microsoft.costmanagement-qpu-retry-after", "60")
            raise RuntimeError(f"Cost Management throttled this call. Retry after {retry}s.")
        if r.status_code == 204:
            return {"columns": [], "rows": []}
        r.raise_for_status()
        props = r.json()["properties"]
        return {"columns": [c["name"] for c in props["columns"]], "rows": props["rows"]}


def _table(result: dict, limit: int = 25) -> list[dict]:
    # Note: the API returns the aggregation's *column* name ("Cost"), not the alias
    # you put in the request body, so normalise to "cost".
    cols = ["cost" if c in ("Cost", "PreTaxCost", "totalCost") else c for c in result["columns"]]
    return [dict(zip(cols, row)) for row in result["rows"][:limit]]


# ---------- MCP tools ----------

@mcp.tool(annotations=READ_ONLY)
async def get_costs(
    group_by: str = "ResourceGroupName",
    timeframe: str = "MonthToDate",
    cost_type: str = "ActualCost",
    scope: str | None = None,
) -> list[dict]:
    """Azure cost for a scope, grouped by a dimension.

    group_by: ResourceGroupName | ServiceName | ResourceLocation | SubscriptionName | MeterCategory
    timeframe: MonthToDate | TheLastMonth | WeekToDate
    cost_type: ActualCost | AmortizedCost
    scope: one of the allowed scopes, e.g. /subscriptions/<id>. Defaults to the first allowed scope.
    """
    body = {
        "type": cost_type,
        "timeframe": timeframe,
        "dataset": {
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": group_by}],
        },
    }
    rows = _table(await _post(_scope(scope), "query", body), limit=100)
    return sorted(rows, key=lambda r: r.get("cost", 0), reverse=True)


@mcp.tool(annotations=READ_ONLY)
async def get_forecast(scope: str | None = None) -> dict:
    """Month-to-date actual cost plus forecast to the end of the current month."""
    today = date.today()
    start = today.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    body = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {"from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"},
        "dataset": {
            "granularity": "Daily",
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
        },
        "includeActualCost": True,
        "includeFreshPartialCost": False,
    }
    rows = _table(await _post(_scope(scope), "forecast", body), limit=62)
    actual = sum(r["cost"] for r in rows if r.get("CostStatus") == "Actual")
    forecast = sum(r["cost"] for r in rows if r.get("CostStatus") == "Forecast")
    currency = rows[0].get("Currency") if rows else None
    return {
        "monthToDate": round(actual, 2),
        "forecastRemaining": round(forecast, 2),
        "projectedMonthTotal": round(actual + forecast, 2),
        "currency": currency,
        "periodEnd": str(end),
        "note": None if forecast else "No forecast rows returned (too little history or spend has stopped); projected total equals actual.",
    }


@mcp.tool(annotations=READ_ONLY)
async def top_spenders(top: int = 5, by: str = "ResourceGroupName", scope: str | None = None) -> list[dict]:
    """Top N cost contributors month-to-date (by ResourceGroupName or ServiceName)."""
    rows = await get_costs(group_by=by, timeframe="MonthToDate", scope=scope)
    return rows[: max(1, min(top, 20))]


@mcp.tool(annotations=READ_ONLY)
def list_scopes() -> list[str]:
    """Scopes this connector is allowed to query."""
    return ALLOWED_SCOPES


# ---------- Inbound auth ----------

class EntraAuth(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return JSONResponse({"error": "missing bearer token"}, status_code=401)
        token = auth.split(" ", 1)[1]
        try:
            key = jwks.get_signing_key_from_jwt(token).key
            jwt.decode(
                token, key, algorithms=["RS256"], audience=AUDIENCE,
                issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            )
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": f"invalid token: {exc}"}, status_code=401)
        return await call_next(request)


app = mcp.streamable_http_app()  # serves /mcp
app.add_middleware(EntraAuth)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
