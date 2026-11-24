# Azure Cost MCP connector for Copilot Cowork (sample)

Read-only MCP server (Python, Streamable HTTP) over the Azure Cost Management Query and Forecast APIs, plus a Cowork plugin (manifest + skill).

**Status:** this is a sample. It compiles but hasn't been tested end to end against a live tenant. Check the manifest schema against the current Cowork plugin docs before you package it.

## Run locally
```bash
pip install -r requirements.txt
az login   # your identity needs Cost Management Reader on the scope
export TENANT_ID=<tenant-guid>
export API_AUDIENCE=api://<server-app-id>
export ALLOWED_SCOPES=/subscriptions/<sub-id>
python server.py   # http://localhost:8000/mcp
```

## Deploy
- Azure Container Apps with a system-assigned managed identity.
- Grant that identity **Cost Management Reader** on each scope in `ALLOWED_SCOPES`.
- Register an Entra app for the API (expose a scope such as `Costs.Read`) and a client registration for Cowork's OAuthPluginVault.

## Package the plugin
Put `manifest.json`, the icons and `skills/` in a zip. Upload it via the Microsoft 365 admin center (Agents > Tools > Registry), or share it to specific people. You can also scaffold it with the wiqd CLI (preview).
