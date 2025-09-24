// Worker: serve static files from /public and proxy API calls to Render.
const API_BASE = "https://api-advisor.onrender.com"; // your Render API (no trailing slash)

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    // Proxy API endpoints
    if (path === "/health" && request.method === "GET") {
      return fetch(`${API_BASE}/health`, { headers: { "cache-control": "no-store" } });
    }
    if (path === "/db/ping" && request.method === "GET") {
      return fetch(`${API_BASE}/db/ping`, { headers: { "cache-control": "no-store" } });
    }
    if (path === "/advice" && request.method === "POST") {
      const body = await request.text();
      return fetch(`${API_BASE}/advice`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body,
      });
    }
    if (request.method === "GET" && url.pathname.startsWith("/finnhub/news")) {
      return fetch(`${API_BASE}${url.pathname}${url.search}`, { headers: { "cache-control": "no-store" } });
    }
    if (request.method === "GET" && url.pathname.startsWith("/finnhub/recommendation")) {
      return fetch(`${API_BASE}${url.pathname}${url.search}`, {
        headers: { "cache-control": "no-store" },
    });
    }
    if (path.startsWith("/analyze/fundamentals_v1") && request.method === "GET") {
  const qs = url.search; // includes ?ticker=...
  return fetch(`${API_BASE}/analyze/fundamentals_v1${qs}`, { headers: { "cache-control": "no-store" } });
    }
    if (path.startsWith("/analyze/news") && request.method === "GET") {
      return fetch(`${API_BASE}/analyze/news${url.search}`, { headers: { "cache-control": "no-store" } });
    }
    if (path.startsWith("/analyze/street") && request.method === "GET") {
      return fetch(`${API_BASE}/analyze/street${url.search}`, { headers: { "cache-control": "no-store" } });
    }
    if (path === "/advice/v1" && request.method === "POST") {
      const body = await request.text();
      return fetch(`${API_BASE}/advice/v1`, { method: "POST", headers: { "content-type":"application/json" }, body });
    }
    if (path === "/analyze/fundamentals" && request.method === "GET") {
      return fetch(`${API_BASE}${url.pathname}${url.search}`, { headers: { "cache-control": "no-store" } });
    }
    if (path.startsWith("/asset/") && request.method === "GET") {
      const ticker = encodeURIComponent(path.slice(7));
      return fetch(`${API_BASE}/asset/${ticker}`, { headers: { "cache-control": "no-store" } });
    }
    if (path === "/ingest/finnhub" && request.method === "GET") {
      return fetch(`${API_BASE}${url.pathname}${url.search}`, {
        headers: { "cache-control": "no-store" },
    });
}

    // Serve static assets from /public via assets binding
    return env.ASSETS.fetch(request);
  }
};