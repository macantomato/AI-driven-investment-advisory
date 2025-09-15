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

