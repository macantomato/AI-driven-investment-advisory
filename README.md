# AI-Driven Investment Advisory (Educational)

An end-to-end demo that pairs a FastAPI backend, a Cloudflare Worker edge UI, and external market data sources (Finnhub, Groq LLM, Neo4j) to generate educational portfolio suggestions. The production backend runs on Render with secrets stored in the Render dashboard; the worker fronts the API and is deployed via Cloudflare.

## Architecture at a Glance

- **FastAPI service (`apps/api`)** – Handles Neo4j persistence, Finnhub ingest, fundamentals/street/news analyzers, and the `/advice/v1` strategy engine.
- **Cloudflare Worker UI (`apps/worker`)** – Browser-facing dashboard that proxies requests to the API and presents the results in an interactive accordion view.
- **Neo4j graph database** – Stores `Asset` and `Sector` nodes. API startup seeds constraints and indexes.
- **Finnhub provider (`apps/api/providers/finnhub.py`)** – Fetches company profiles, metrics, recommendations, and headlines.
- **Groq LLM (OpenAI-compatible)** – Optional; supplies natural-language rationale when `GROQ_API_KEY` is present. The API falls back to deterministic reasoning if not.

```
browser ↔ Cloudflare Worker ↔ Render FastAPI ↔ Neo4j
                                  ↘ Finnhub (REST)
                                  ↘ Groq LLM (optional)
```

Production Render/Cloudflare projects already have environment variables for Neo4j, Finnhub, and Groq. Nothing sensitive is committed to git.

## Getting Started Locally

### Prerequisites

- Python 3.10+
- Node.js 18+
- Access to a Neo4j instance (local AuraDB or self-hosted)
- Finnhub API key (free tier is fine)
- Optional Groq API key for LLM explanations

### Clone & Configure

```bash
git clone https://github.com/<your-org>/AI-driven-investment-advisory.git
cd AI-driven-investment-advisory
```

Create `.env` in `apps/api` (or export variables) with:

```
NEO4J_URI=bolt+s://<host>:<port>
NEO4J_USER=<user>
NEO4J_PASS=<password>
FINNHUB_API_KEY=<key>
GROQ_API_KEY=<optional key>
```

Render already contains these values; re-use them locally or define new ones.

## Backend (FastAPI) – `apps/api`

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /health` – service check
- `GET /db/ping` – confirm Neo4j connectivity
- `GET /ingest/finnhub?tickers=AAPL&include=metrics` – sample ingest
- `POST /advice/v1` – build a strategy: `{"tickers":["AAPL","NVDA"],"risk":3}`

Interactive docs live at `http://localhost:8000/docs`.

## Worker UI – `apps/worker`

The worker proxies browser calls to the API. For local development you can point it at your local FastAPI instance.

1. Update `apps/worker/src/index.js` if you need `API_BASE = "http://localhost:8000"`.
2. Install deps and run the dev server:

   ```bash
   cd apps/worker
   npm install
   npm run dev
   ```

3. Visit `http://localhost:8787` to use the dashboard against your API.

Deployment uses `wrangler.toml`; run `npm run deploy` when ready, making sure Cloudflare Worker secrets mirror the Render API URL if it changes.

## Strategy Builder Flow

1. Worker collects tickers and risk, POSTs to `/advice/v1`.
2. API pulls fundamentals, street sentiment, and recent news for each ticker, derives combined signals, normalizes allocations, and optionally asks Groq to refine the narrative.
3. Worker renders collapsible sections per ticker (Fundamentals, Street, News, Signals) plus an Allocation Plan dropdown with weights and rationale.

External failures degrade gracefully (e.g., missing Groq key → deterministic rationale; Finnhub hiccup → partial data without crashing).

## Deployment Notes

- **Render** – Hosts the FastAPI service. Configure the environment variables above in the Render dashboard. Redeploys trigger automatically on pushes to the tracked branch.
- **Cloudflare Worker** – Deployed separately. Update the worker when UI or proxy logic changes.

## Troubleshooting

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| `/advice/v1` returns 500 | Neo4j or Finnhub credentials missing | Confirm env vars locally/Render |
| Allocation is empty or uniform | Finnhub metrics/news not available | Ingest assets, check API key quota |
| Worker shows "Request failed" | API unreachable from worker | Verify `API_BASE` and API health |
| Rationale says "LLM not configured" | `GROQ_API_KEY` not set | Provide Groq key or accept fallback |

## Contributing

1. Fork or create a feature branch.
2. Make changes and run the API & worker locally.
3. Commit with clear messages, push, and open a PR.

## License

See [LICENSE](LICENSE) (MIT).

