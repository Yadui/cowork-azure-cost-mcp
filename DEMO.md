# Recording the demo: Azure cost insights in Copilot Cowork

Target length is 3–5 minutes. Do the prep a day ahead: role assignments, consent and cost data all take time to show up.

## 0. What you need
- A tenant where you have a **Microsoft 365 Copilot license** and Cowork is enabled.
- **AI Administrator** or **Global Administrator** in that tenant, or someone who can approve the plugin. Sharing it only to yourself doesn't need approval.
- An Azure subscription **with real spend** in at least 3–4 resource groups. A brand-new subscription shows ₹0 and makes a dull demo. If yours is empty, deploy a few cheap resources about 2 days before recording, since cost data lags by up to 24h.
- Azure CLI, Python 3.11+, and a screen recorder (OBS, or Clipchamp/Teams if you want it simple).

## 1. Run the server locally first (5 min)
Test the tools before any Cowork wiring:
```bash
cd sample && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```
```bash
az login
```
```bash
export TENANT_ID=<tenant-guid> API_AUDIENCE=api://<server-app-id> ALLOWED_SCOPES=/subscriptions/<sub-id>
```
```bash
python server.py
```
Test with the MCP Inspector:
```bash
npx @modelcontextprotocol/inspector
```
Point it at `http://localhost:8000/mcp` and use a token from `az account get-access-token --resource api://<server-app-id>`. Call `get_forecast` and `top_spenders` and check that the numbers match Cost Analysis in the portal. **This also checks VERIFY.md item 9, the `CostStatus` column.**

## 2. Entra app for the MCP server
1. Entra admin center > App registrations > New: **azure-cost-mcp**.
2. Expose an API: set the App ID URI to `api://<app-id>` and add the scope **Costs.Read**.
3. Manifest: set `"accessTokenAcceptedVersion": 2` (VERIFY.md item 13).
4. Create a client secret. Cowork's OAuth registration needs it, and the server doesn't.

## 3. Deploy to Azure Container Apps
```bash
az containerapp up -n azure-cost-mcp -g rg-cowork-demo -l centralindia --source sample --ingress external --target-port 8000 --env-vars TENANT_ID=<tid> API_AUDIENCE=api://<app-id> ALLOWED_SCOPES=/subscriptions/<sub-id>
```
`az containerapp up --source` needs a Dockerfile or a buildpack-detectable app. If it complains, add a 3-line Dockerfile (`FROM python:3.12-slim`, `pip install -r requirements.txt`, `CMD python server.py`).
```bash
az containerapp identity assign -n azure-cost-mcp -g rg-cowork-demo --system-assigned
```
```bash
az role assignment create --assignee <identity-principal-id> --role "Cost Management Reader" --scope /subscriptions/<sub-id>
```
Wait about 10 minutes for the role to propagate, then repeat the Inspector test against `https://<fqdn>/mcp`.

## 4. OAuth registration for the plugin vault
Register the OAuth client, which gives you the `referenceId` for the manifest. I believe this is done in the Teams Developer Portal (Tools > OAuth client registration). **Confirm where it lives in the current Cowork plugin docs.**
- Authorization endpoint `https://login.microsoftonline.com/<tid>/oauth2/v2.0/authorize`, token endpoint `.../token`
- Client ID and secret from step 2, scope `api://<app-id>/Costs.Read`
- Base URL: your Container Apps FQDN
- Add the redirect URI it gives you to the app registration.

## 5. Package and install the plugin
1. Put the `referenceId` and `mcpServerUrl` into `sample/plugin/manifest.json`, and generate a new GUID for `id`.
2. Add `color.png` (192×192) and `outline.png` (32×32, transparent).
3. Zip **the contents** of `sample/plugin/` (manifest at the zip root).
4. Share it with yourself: Cowork > plugins/manage > upload. For an org-wide demo, upload it in the M365 admin center (Agents > Tools > Registry) and approve it. Alternatively, `wiqd` (preview) can scaffold and validate the package; use it if the manifest gets rejected.
5. Open Cowork and check that the Azure Cost connector shows up. Sign in when prompted, which is the OAuth consent.

## 6. Seed the Work IQ context (the part that makes the demo land)
Do this **1–2 days before recording** so it's indexed:
- Send yourself an email from a colleague or test account: *"Budget alert: prod subscription has hit 80% of the ₹X monthly budget"*.
- Post a Teams chat message: *"rg-data-platform is Priya's team; rg-ai-sandbox belongs to the AI CoE"*, using your real top resource group names.
- Optional: add `owner` tags on the resource groups so you can show both sources.

## 7. Dry run (record nothing yet)
Run the exact demo prompt twice. Check:
- that the figures match Cost Analysis,
- that it finds the budget email and the owners,
- that it stops for approval before sending mail.

If it calls tools repeatedly or gets throttled, wait a few minutes. The limit is 12 QPU per 10 seconds per tenant.

## 8. Recording script (~4 min)
| Time | On screen | Say |
|---|---|---|
| 0:00 | Azure Cost Analysis in the portal | "Here's the number. What's missing is who owns the spend and why it's up." |
| 0:20 | Architecture diagram (Figure 1) | Cowork, skill, MCP server and Work IQ in one sentence each |
| 0:50 | VS Code: `server.py` tools and auth middleware | "Four read-only tools, allow-listed scopes, Entra token check" |
| 1:30 | The skill markdown | Point at the Work IQ step and the "never guess numbers" rule |
| 1:50 | Cowork: type *"Run my weekly Azure cost review for the production subscription"* | Let the plan appear. Narrate the tool calls as they run |
| 2:40 | Result: forecast, top spenders table, owners from mail/Teams | Compare one figure to the portal tab |
| 3:20 | Draft email to owners, approval prompt | "It drafts, I approve. Nothing goes out on its own." Approve or cancel |
| 3:40 | Close | One of the flaws (auth or throttling) plus next step (on-behalf-of per-user RBAC) |

Background runs can take minutes, so record the Cowork segment in one take and **cut the waiting** in editing. Don't fake it.

## 9. Recording hygiene
- Hide or blur subscription IDs, tenant IDs, the FQDN, colleague names and email addresses. Use a demo tenant if you can.
- Use 1080p, 125–150% zoom in VS Code and the browser, and Do Not Disturb on.
- Capture the stills for blog Figures 1–2 from the same run. Then remove the TODOs in `blog.md` and rewrite "flaws I hit" from what actually happened.
- After the demo, delete `rg-cowork-demo` or scale the app to zero, and remove the role assignment.
