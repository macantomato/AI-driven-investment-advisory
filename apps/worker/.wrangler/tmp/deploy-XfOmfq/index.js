// src/index.js
var API_BASE = "https://api-advisor.onrender.com";
var index_default = {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    if (path === "/health" && request.method === "GET") {
      return fetch(`${API_BASE}/health`, { headers: { "cache-control": "no-store" } });
    }
    if (path === "/advice" && request.method === "POST") {
      const body = await request.text();
      return fetch(`${API_BASE}/advice`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body
      });
    }
    return env.ASSETS.fetch(request);
  }
};
export {
  index_default as default
};
//# sourceMappingURL=index.js.map
