const API_BASE = "https://api-advisor.onrender.com";
const NO_STORE = { "cache-control": "no-store" };

async function proxyGet(path, search = "") {
  return fetch(`${API_BASE}${path}${search}`, { headers: NO_STORE });
}

async function proxyJson(request, path) {
  const body = await request.text();
  const headers = { "content-type": request.headers.get("content-type") || "application/json" };
  return fetch(`${API_BASE}${path}`, {
    method: request.method,
    headers,
    body,
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const pathname = url.pathname;
    const path = pathname.replace(/\/+$/, "") || "/";
    const method = request.method.toUpperCase();

    if (method === "GET" && path === "/health") {
      return proxyGet("/health");
    }
    if (method === "GET" && path === "/db/ping") {
      return proxyGet("/db/ping");
    }

    if (method === "POST" && path === "/advice") {
      return proxyJson(request, "/advice");
    }
    if (method === "POST" && path === "/advice/v1") {
      return proxyJson(request, "/advice/v1");
    }

    if (method === "GET" && path === "/ingest/finnhub") {
      return proxyGet(path, url.search);
    }

    if (method === "GET" && pathname.startsWith("/finnhub/news")) {
      return proxyGet(pathname, url.search);
    }
    if (method === "GET" && pathname.startsWith("/finnhub/recommendation")) {
      return proxyGet(pathname, url.search);
    }

    if (method === "GET" && path === "/analyze/fundamentals") {
      return proxyGet(path, url.search);
    }
    if (method === "GET" && path === "/analyze/fundamentals_v1") {
      return proxyGet(path, url.search);
    }
    if (method === "GET" && path === "/analyze/news") {
      return proxyGet(path, url.search);
    }
    if (method === "GET" && path === "/analyze/street") {
      return proxyGet(path, url.search);
    }
    if (method === "POST" && path === "/analyze/news_refine") {
      return proxyJson(request, "/analyze/news_refine");
    }

    if (method === "GET" && path.startsWith("/asset/")) {
      const ticker = pathname.slice("/asset/".length);
      const encoded = encodeURIComponent(ticker);
      return fetch(`${API_BASE}/asset/${encoded}`, { headers: NO_STORE });
    }

    if (method === "GET" && path.startsWith("/finnhub")) {
      return proxyGet(pathname, url.search);
    }

    return env.ASSETS.fetch(request);
  }
};
