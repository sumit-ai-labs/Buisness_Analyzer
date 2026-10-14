# Business Disruption Early-Warning System

A web application where a business defines its network of suppliers, facilities, warehouses, and transport routes; the system continuously watches for real-world disruptions (floods, strikes, closures, supplier failures), uses AI to extract structured events, connects events to network nodes via graph traversal, deterministically scores risk, and raises early alerts.

## Pipeline Architecture
1. **Detect** — Research Agent queries Tavily per entity & location with attributable URLs.
2. **Understand** — Analysis Agent extracts `DisruptionEvent` via LLM + Pydantic v2 structured output with false-positive filtering.
3. **Connect** — Entity Matcher maps events to NetworkX graph nodes & downstream dependencies (`get_downstream`).
4. **Assess** — Deterministic Risk Engine scores risk (0-100) using a 5-factor transparent formula.
5. **Alert** — Alert Generator templates & deduplicates actionable alerts for the dashboard.

## Tech Stack
- **Backend**: Python 3.13, FastAPI, NetworkX, Pydantic v2, Tavily API, OpenAI/Anthropic
- **Frontend**: React, TypeScript, Vite, Tailwind CSS, React Flow (`@xyflow/react`)
- **Package Management**: `uv`, `npm`

## Quick Start

### 1. Backend
```bash
cd backend
cp .env.example .env
# Edit .env to supply TAVILY_API_KEY and LLM_API_KEY
uvicorn app.main:app --reload --port 8000
```
API Documentation will be available at `http://localhost:8000/docs`.

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
Dashboard will be available at `http://localhost:5173`.

The Vite development server proxies `/api` to `http://127.0.0.1:8000` by default. Override with `VITE_API_PROXY_TARGET` only when the backend intentionally runs on another port.

## API Contract Notes

- `GET /api/events` returns full `DisruptionEvent` objects for verified, non-gated events.
- `GET /api/events/unconfirmed` returns gated event summaries, not full `DisruptionEvent` objects. These summaries use `event_id` and include credibility fields such as `authenticity_score`, `confidence_label`, `source_tier`, and `geo_status`.
- `GET /api/alerts` returns bare `Alert` objects. It does not include nested `risk_assessment`, `event`, or entity payloads.
- `GET /api/alerts/{id}/explain` returns the expanded detail payload with `alert`, `event`, `risk_assessment`, `credibility_assessment`, `geo_verification`, `impacted_entities`, and `last_monitored_at`.
- `GET /api/dashboard/stats` returns aggregate counts, including unconfirmed event and location ambiguity counts.

## Reliability Behavior

- News recency is strict by default: results older than `SEARCH_RECENCY_DAYS` are dropped, and undated results are dropped unless `SEARCH_KEEP_UNDATED_RESULTS=true`.
- Article extraction failures are isolated per source result. One failed LLM/provider extraction is logged with source identifiers and a short error summary, then the remaining articles continue.
- Monitoring responses include extraction counts: processed, successful, failed, rejected, relevant, gated, ambiguous, assessments, and new alerts.
- Geographic verification is computed once per event during a monitoring cycle and reused by entity matching. Ambiguous locations remain gated from network impact propagation.
- Weather telemetry affects flood/weather credibility: confirming rain or wind adds corroboration, while checked local weather below threshold reduces credibility.
