const panels = {
  health: document.getElementById("outHealth"),
  db: document.getElementById("outDb"),
  asset: document.getElementById("outAsset"),
  ingest: document.getElementById("outIngest"),
  fund: document.getElementById("outFund"),
  street: document.getElementById("outStreet"),
  news: document.getElementById("outNewsSummary"),
  advice: document.getElementById("outAdvice"),
};

const newsListEl = document.getElementById("newsList");
const newsState = { ticker: "", items: [] };

const showJson = (el, data) => { el.textContent = JSON.stringify(data, null, 2); };
const showError = (el, error) => showJson(el, { error: String(error) });
const showLoading = (el, label) => showJson(el, { loading: label });

async function fetchJson(url, options = {}) {
  const res = await fetch(url, { cache: "no-store", ...options });
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); }
    catch { throw new Error(`Expected JSON, got: ${text.slice(0, 200)}`); }
  }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : text;
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${detail}`);
  }
  return data ?? {};
}

function getInputValue(id) {
  return (document.getElementById(id).value || "").trim();
}

function parseTickerList(raw) {
  return Array.from(new Set((raw || "").split(/[\s,]+/).filter(Boolean)))
    .slice(0, 50)
    .map((t) => t.toUpperCase());
}

function renderNewsList(items) {
  newsListEl.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "news-item";
    empty.textContent = "No headlines loaded.";
    newsListEl.appendChild(empty);
    return;
  }

  const fragment = document.createDocumentFragment();
  items.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "news-item";

    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = String(index);
    checkbox.dataset.index = String(index);
    checkbox.checked = true;

    const textWrap = document.createElement("div");
    const headline = document.createElement("span");
    headline.className = "news-headline";
    headline.textContent = item.headline || "(no headline)";
    textWrap.appendChild(headline);

    const metaParts = [];
    const dateValue = item.date || item.datetime || item.publishedAt;
    if (dateValue) {
      try {
        const parsed = new Date(dateValue);
        if (!Number.isNaN(parsed.getTime())) {
          metaParts.push(parsed.toLocaleString());
        }
      } catch (err) {
        /* ignore date parsing issues */
      }
    }
    if (item.source) {
      metaParts.push(item.source);
    }
    if (metaParts.length) {
      const meta = document.createElement("span");
      meta.className = "news-meta";
      meta.textContent = metaParts.join(" | ");
      textWrap.appendChild(meta);
    }

    label.appendChild(checkbox);
    label.appendChild(textWrap);
    row.appendChild(label);
    fragment.appendChild(row);
  });

  newsListEl.appendChild(fragment);
}

function selectedHeadlines() {
  return Array.from(newsListEl.querySelectorAll('input[type="checkbox"]:checked'))
    .map((input) => {
      const idx = Number(input.dataset.index);
      const item = newsState.items[idx];
      return item && typeof item.headline === "string" ? item.headline.trim() : "";
    })
    .filter(Boolean);
}

// System

document.getElementById("btnHealth").addEventListener("click", async () => {
  showLoading(panels.health, "/health");
  try { showJson(panels.health, await fetchJson("/health")); }
  catch (err) { showError(panels.health, err); }
});

document.getElementById("btnDb").addEventListener("click", async () => {
  showLoading(panels.db, "/db/ping");
  try { showJson(panels.db, await fetchJson("/db/ping")); }
  catch (err) { showError(panels.db, err); }
});

// Lookup & ingest

document.getElementById("btnAsset").addEventListener("click", async () => {
  const ticker = getInputValue("assetTicker");
  if (!ticker) { showError(panels.asset, "Enter a ticker."); return; }
  showLoading(panels.asset, `/asset/${ticker}`);
  try { showJson(panels.asset, await fetchJson(`/asset/${encodeURIComponent(ticker)}`)); }
  catch (err) { showError(panels.asset, err); }
});

document.getElementById("btnIngest").addEventListener("click", async () => {
  const tickers = parseTickerList(getInputValue("ingestTickers"));
  if (!tickers.length) {
    showError(panels.ingest, "Enter 1-50 tickers.");
    return;
  }
  const qsTickers = tickers.map((t) => `tickers=${encodeURIComponent(t)}`).join("&");
  const include = document.getElementById("includeMetrics").checked ? "&include=metrics" : "";
  const url = `/ingest/finnhub?${qsTickers}${include}`;
  showLoading(panels.ingest, url);
  try { showJson(panels.ingest, await fetchJson(url)); }
  catch (err) { showError(panels.ingest, err); }
});

// Analyzers

document.getElementById("btnFund").addEventListener("click", async () => {
  const ticker = getInputValue("anTicker");
  if (!ticker) { showError(panels.fund, "Enter a ticker."); return; }
  const url = `/analyze/fundamentals_v1?ticker=${encodeURIComponent(ticker)}`;
  showLoading(panels.fund, url);
  try { showJson(panels.fund, await fetchJson(url)); }
  catch (err) { showError(panels.fund, err); }
});

document.getElementById("btnStreet").addEventListener("click", async () => {
  const ticker = getInputValue("anTicker");
  if (!ticker) { showError(panels.street, "Enter a ticker."); return; }
  const url = `/analyze/street?ticker=${encodeURIComponent(ticker)}`;
  showLoading(panels.street, url);
  try { showJson(panels.street, await fetchJson(url)); }
  catch (err) { showError(panels.street, err); }
});

document.getElementById("btnNewsLoad").addEventListener("click", async () => {
  const ticker = getInputValue("newsTicker");
  const days = Number(document.getElementById("newsDays").value || 30);
  const limit = Number(document.getElementById("newsLimit").value || 8);
  if (!ticker) { showError(panels.news, "Enter a news ticker."); return; }

  const url = `/finnhub/news/${encodeURIComponent(ticker)}?days=${encodeURIComponent(days)}&limit=${encodeURIComponent(limit)}`;
  showLoading(panels.news, url);
  newsState.ticker = ticker;
  newsState.items = [];
  renderNewsList([]);
  try {
    const data = await fetchJson(url);
    const items = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
    newsState.items = items.slice(0, limit);
    renderNewsList(newsState.items);
    showJson(panels.news, { ticker, loaded: newsState.items.length });
  } catch (err) {
    showError(panels.news, err);
  }
});

document.getElementById("btnNewsSummarize").addEventListener("click", async () => {
  const ticker = newsState.ticker;
  const headlines = selectedHeadlines();
  if (!ticker) { showError(panels.news, "Load news first."); return; }
  if (!headlines.length) { showError(panels.news, "Select at least one headline."); return; }

  showLoading(panels.news, "/analyze/news_refine");
  try {
    const payload = { ticker, headlines };
    const data = await fetchJson("/analyze/news_refine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    showJson(panels.news, data);
  } catch (err) {
    showError(panels.news, err);
  }
});

// Master advice

document.getElementById("btnAdvice").addEventListener("click", async () => {
  const tickers = parseTickerList(getInputValue("adviceTickers")).slice(0, 10);
  const riskRaw = Number(document.getElementById("adviceRisk").value || 3);
  const risk = Number.isFinite(riskRaw) ? Math.min(5, Math.max(1, Math.round(riskRaw))) : 3;
  if (!tickers.length) {
    showError(panels.advice, "Enter at least one ticker.");
    return;
  }
  showLoading(panels.advice, "/advice/v1");
  try {
    const data = await fetchJson("/advice/v1", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers, risk }),
    });
    showJson(panels.advice, data);
  } catch (err) {
    showError(panels.advice, err);
  }
});
