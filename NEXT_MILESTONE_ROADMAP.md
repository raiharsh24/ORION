# FRIDAY AI OS — Next Milestone Roadmap: "Resilient Agent Core & Gateway Correctness"

> Prepared from Runtime Stabilization verification (2026-07-08). **No features implemented** — roadmap only.
> Prerequisite state: runtime pipeline stable (Health 84/100, Production Readiness 67/100). No critical bugs.

## Theme
Harden the agentic/tool layer and gateway correctness on top of the now-stable runtime foundation. Do **not** redesign architecture.

## P1 — Resilience & Correctness (must-do)
1. **Configurable LLM fallback** on Gemini failure (quota/network): keep surfacing the real error in logs, but return a mock/cached response so the assistant stays usable during outages. (Issue R2)
2. **Fix gateway proxy routing**: replace the hand-maintained target list in `proxyMiddleware.js` with a catch-all or OpenAPI-derived filter so `/runtime/*`, `/planner/*` etc. are reachable. (R1 / A1)
3. **Enable authentication**: enforce `FRIDAY_API_KEY`/`FRIDAY_SECRET` for non-local deployments; remove `FRIDAY_AUTH_DISABLED=true` default. (S1)
4. **Sandbox the terminal tool**: command allow/deny-list + working-directory jail before any untrusted use. (S2)

## P2 — Tool & Intent Quality
5. **LLM-guided tool gating**: stop keyword ("write"/"create") matching that hijacks conversational prompts into file-write tools. (R3)
6. **Short-circuit multi-LLM-call overhead** for plain `CHAT` intents (intent + planner intercept + generation currently ~3× quota burn). (R4)
7. **Migrate SDK** `google.generativeai` → `google.genai`; set default model to a current one (not deprecated `gemini-1.5-flash`). (R6/R7)

## P3 — Maintainability & Coverage
8. Remove debug `print("[DEBUG ROUTE]...")` in `app/api/routes.py`; narrow the 172 broad `except Exception:` clauses. (R5/R8)
9. **CI tests** for: gemini fallback path, mission cancel route, gateway proxy ordering, planner lazy-init.
10. Structured error/metrics sampling for LLM failures.

## Stretch (post-milestone)
- Shared session/memory store (Redis/Postgres) for multi-instance scaling. (A2)
- Explicit `LLM_MODE=mock|real` setting replacing string-sentinel mock detection. (A3)

## Exit criteria for this milestone
- Gemini outage/quota → graceful degraded response, no hard error.
- All FastAPI routes reachable through the gateway.
- Auth on by default; terminal tool sandboxed.
- Conversational prompts never routed to destructive tools.
- New changes covered by CI; no debug prints in routed paths.
