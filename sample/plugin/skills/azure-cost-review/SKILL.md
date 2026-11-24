---
name: azure-cost-review
description: Weekly Azure cost review. Use when the user asks about Azure spend, budgets, forecasts, cost spikes or which team or resource group is driving cost.
---

# Azure cost review

1. Call `list_scopes` if the user hasn't named a subscription.
2. Call `get_forecast` for the scope. Report month-to-date, projected month total and currency.
3. Call `top_spenders` (top 5, by ResourceGroupName). If one group is over 40% of spend, call `get_costs` with `group_by=ServiceName` and explain what drives it.
4. Use Work IQ to find context: search the user's mail and Teams chats from the last 14 days for the top resource group names and any "budget" or "cost alert" emails. Quote who owns each top spender if you find it.
5. Produce a short summary: a table of top spenders, the forecast versus any budget mentioned in mail, and up to three suggested follow-ups (owner + action).
6. Before sending mail or posting in Teams, show the draft and ask for approval.

Rules:
- Never guess numbers. Every figure must come from a tool result.
- Cost data refreshes about every 4 hours, and the API is throttled. Don't call the same tool twice for the same inputs in one run.
- Always state the currency and whether figures are actual or amortized.
