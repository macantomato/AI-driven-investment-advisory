const out = document.getElementById("out");
const show = (obj) => { out.textContent = JSON.stringify(obj, null, 2); };

async function fetchJson(url, options = {}) {
  const res = await fetch(url, { cache: "no-store", ...options });
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); }
    catch { throw new Error(`Expected JSON, got: ${text.slice(0,200)}`); }
  }
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}: ${text}`);
  return data ?? {};
}

document.getElementById("btnHealth").onclick = async () => {
  show({ loading: "/health" });
  try { show(await fetchJson("/health")); } catch (e) { show({ error: String(e) }); }
};

document.getElementById("btnDbPing").onclick = async () => {
    show({ loading: "/db/ping" });
    try { show(await fetchJson("/db/ping")); } catch (e) { show({ error: String(e) }); }
}

document.getElementById("btnAsset").onclick = async () => {
    const t = document.getElementById("assetTicker").value;
    show({ Loading: `/asset/${t}`});
    try { show(await fetchJson(`/asset/${encodeURIComponent(t)}`)); }
    catch (e) { show({ error: String(e) }); }
};

document.getElementById("btnIngestFinnhub").onclick = async () => {
    const raw = document.getElementById("ingestFinnhubTickers").value || "";
    const array = Array.from(new Set(raw.split(/[,\s]+/).filter(Boolean)))
                   .slice(0, 50)
                   .map(s => s.toUpperCase());
  if (!array.length) {
    show({ error: "Enter 1–50 tickers (comma or space separated)" });
    return;
  }
  // reapeated tickers
  const qs = array.map(t => `tickers=${encodeURIComponent(t)}`).join("&");

  show({ loading: `/ingest/finnhub?${qs}` });
  try {
    const data = await fetchJson(`/ingest/finnhub?${qs}`);
    show(data); 
  } catch (e) {
    show({ error: String(e) });
  }
};



document.getElementById("btnAdvice").onclick = async () => {
  show({ loading: "/advice" });
  try {
    const body = { risk: 3, universe: ["AAPL", "MSFT", "JNJ"] };
    const data = await fetchJson("/advice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    show(data);
  } catch (e) { show({ error: String(e) }); }
};

