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
  const qsTickers = array.map(t => `tickers=${encodeURIComponent(t)}`).join("&");
  const include = document.getElementById("includeMetrics").checked ? "&include=metrics" : "";

  show({ loading: `/ingest/finnhub?${qsTickers}${include}` });
  try {
    const data = await fetchJson(`/ingest/finnhub?${qsTickers}${include}`);
    show(data);
  } catch (e) {
    show({ error: String(e) });
  }
};

document.getElementById("btnFinnhubRec").onclick = async () => {
  const t = document.getElementById("finnhubTicker").value.trim();
  const recOut = document.getElementById("finnOut");
  recOut.textContent = JSON.stringify({ loading: `/finnhub/recommendation/${t}` }, null, 2);

  try {
    const res = await fetch(`/finnhub/recommendation/${encodeURIComponent(t)}`, { cache: "no-store" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    recOut.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    recOut.textContent = JSON.stringify({ error: String(err) }, null, 2);
  }
};

document.getElementById("btnFund").onclick = async () => {
  const t = (document.getElementById("fundTicker").value || "").trim();
  const fundOut = document.getElementById("fundOut");
  if (!t) { fundOut.textContent = JSON.stringify({ error: "Enter a ticker" }, null, 2); return; }

  fundOut.textContent = JSON.stringify({ loading: `/analyze/fundamentals?ticker=${t}` }, null, 2);
  try {
    const data = await fetchJson(`/analyze/fundamentals?ticker=${encodeURIComponent(t)}`);
    fundOut.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    fundOut.textContent = JSON.stringify({ error: String(e) }, null, 2);
  }
};

document.getElementById("btnNews").onclick = async () => {
  const t = (document.getElementById("newsTicker").value || "").trim();
  const d = Number(document.getElementById("newsDays").value || 30);
  const newsOut = document.getElementById("newsOut");

  if (!t) { newsOut.textContent = JSON.stringify({ error: "Enter a ticker" }, null, 2); return; }
  newsOut.textContent = JSON.stringify({ loading: `/finnhub/news/${t}?days=${d}` }, null, 2);

  try {
    const res = await fetch(`/finnhub/news/${encodeURIComponent(t)}?days=${encodeURIComponent(d)}`, { cache: "no-store" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    newsOut.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    newsOut.textContent = JSON.stringify({ error: String(err) }, null, 2);
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

document.getElementById("btnFundV1").onclick = async () => {
  const t = document.getElementById("assetTicker").value.trim();
  try { show(await fetchJson(`/analyze/fundamentals_v1?ticker=${encodeURIComponent(t)}`)); }
  catch (e) { show({ error: String(e) }); }
};

document.getElementById("btnNews").onclick = async () => {
  const t = document.getElementById("assetTicker").value.trim();
  try { show(await fetchJson(`/analyze/news?ticker=${encodeURIComponent(t)}&days=30&limit=8`)); }
  catch (e) { show({ error: String(e) }); }
};

document.getElementById("btnStreet").onclick = async () => {
  const t = document.getElementById("assetTicker").value.trim();
  try { show(await fetchJson(`/analyze/street?ticker=${encodeURIComponent(t)}`)); }
  catch (e) { show({ error: String(e) }); }
};

document.getElementById("btnAdviceV1").onclick = async () => {
  const raw = document.getElementById("ingestFinnhubTickers").value || "";
  const arr = Array.from(new Set(raw.split(/[,\s]+/).filter(Boolean))).slice(0,10).map(s=>s.toUpperCase());
  try {
    show(await fetchJson("/advice/v1", {
      method:"POST", headers:{ "Content-Type":"application/json" },
      body: JSON.stringify({ tickers: arr.length ? arr : ["AAPL","MSFT","JNJ"], risk: 3 })
    }));
  } catch (e) { show({ error: String(e) }); }
};

