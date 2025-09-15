// Minimal Cloudflare Worker: serves a tiny HTML UI and proxies to your Render API.
const API_BASE = "https://api-advisor.onrender.com"; // <-- your Render URL (no trailing slash)
const DISCLAIMER = "Educational only — NOT financial advice.";

function html(body) {
  return new Response(
    `<!doctype html>
<meta charset="utf-8">
<title>AI-Driven Investment Advisor (Educational)</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 880px; margin: 40px auto; padding: 16px; }
  pre { background:#111;color:#0f0;padding:12px;border-radius:8px;overflow:auto; }
  button { padding:8px 12px; }
  .muted{opacity:.7;font-size:12px}
</style>
<h1>AI-Driven Investment Advisor (Educational)</h1>
<p class="muted"><strong>Disclaimer:</strong> ${DISCLAIMER}</p>
<div style="display:flex;gap:12px;margin-top:16px">
  <button id="btnHealth">Health</button>
  <button id="btnAdvice">Get Advice</button>
</div>
<p class="muted">API (proxied): ${API_BASE}</p>
<div id="out" style="margin-top:20px"></div>
<script>
const out = document.getElementById('out');
function show(obj, color="#0f0"){ out.innerHTML = '<pre style="color:'+color+'">'+JSON.stringify(obj,null,2)+'</pre>'; }
async function safeFetch(url, opts){
  const res = await fetch(url, Object.assign({headers:{}, cache:"no-store"}, opts||{}));
  const text = await res.text();
  let data=null; if(text){ try{ data=JSON.parse(text);}catch{ data={raw:text}; } }
  if(!res.ok) throw new Error("HTTP "+res.status+" "+res.statusText+" "+(text||""));
  return data ?? {ok:true};
}
document.getElementById('btnHealth').onclick = async () => {
  show({loading:"/health"},"#0ff");
  try { show(await safeFetch('/health'),"#0ff"); } catch(e){ show({error:String(e)},"#f66"); }
};
document.getElementById('btnAdvice').onclick = async () => {
  show({loading:"/advice"},"#0ff");
  try {
    const body = { risk:3, universe:["AAPL","MSFT","JNJ"] };
    const data = await safeFetch('/advice', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    show(data,"#0ff");
  } catch(e){ show({error:String(e)},"#f66"); }
};
</script>`,
    { headers: { "content-type": "text/html; charset=utf-8" } }
  );
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (path === "/") return html();

    // Proxy GET /health -> Render
    if (path === "/health" && request.method === "GET") {
      return fetch(`${API_BASE}/health`, { headers: { "cache-control": "no-store" } });
    }

    // Proxy POST /advice -> Render
    if (path === "/advice" && request.method === "POST") {
      const body = await request.text();
      return fetch(`${API_BASE}/advice`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body
      });
    }

    return new Response(JSON.stringify({ error: "Not Found", path }), { status: 404, headers: { "content-type": "application/json" } });
  }
};
