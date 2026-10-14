# Business Disruption Early-Warning System - Backend

FastAPI backend service powering the Detect -> Understand -> Connect -> Assess -> Alert early warning pipeline.

## Structure
- `app/models/`: Pydantic v2 schemas (`entity.py`, `events.py`, `risk.py`)
- `app/services/`: Business logic services (`network_service.py`, `research_service.py`, `analysis_service.py`, `risk_service.py`, `alert_service.py`)
- `app/api/`: FastAPI route handlers (`entities.py`, `relationships.py`, `network.py`, `alerts.py`, `auth.py`)
- `app/core/`: Configuration, logging, security, and LLM/Tavily integrations
- `tests/`: Pytest test suite

## Running Locally
```bash
uvicorn app.main:app --reload --port 8000
```

The frontend development proxy expects the backend at `http://127.0.0.1:8000` by default.

## Contract and Reliability Notes

- `/api/events` returns full verified `DisruptionEvent` objects.
- `/api/events/unconfirmed` returns compact review summaries for credibility-gated events. It does not return the complete event schema.
- `/api/alerts` returns bare alert records. Use `/api/alerts/{id}/explain` for nested event, risk, credibility, geo, and impacted entity details.
- The analysis pipeline isolates extraction failures per article and returns batch counters in `/api/monitor/run`.
- The monitoring pipeline reuses the geographic verification result during matching and preserves the ambiguity gate.
- News fetching uses a 7-day default recency window and drops undated results unless `SEARCH_KEEP_UNDATED_RESULTS=true`.
- Flood/weather events use Open-Meteo telemetry as an independent signal. Weather confirmation boosts corroboration; checked weather below threshold reduces credibility.
