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
    if (path === "/finnhub/recommendation" && request.method === "GET") {
      return fetch(`${API_BASE}${url.pathname}${url.search}`, {
        headers: { "cache-control": "no-store" },
      });
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