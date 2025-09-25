const panels = {
  health: document.getElementById("resultHealth"),
  db: document.getElementById("resultDb"),
  asset: document.getElementById("resultAsset"),
  ingest: document.getElementById("resultIngest"),
  fund: document.getElementById("resultFund"),
  street: document.getElementById("resultStreet"),
  news: document.getElementById("resultNews"),
  advice: document.getElementById("resultAdvice"),
};

const newsListEl = document.getElementById("newsList");
const newsState = { ticker: "", items: [] };

const MAX_LIST_ITEMS = 12;

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatNumber(value) {
  if (!Number.isFinite(value)) {
    return escapeHtml(value);
  }
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(2)} T`;
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)} B`;
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(2)} M`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(2)} K`;
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function prettifyKey(key) {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/^./, (char) => char.toUpperCase());
}

function renderScalar(value) {
  if (value === null || value === undefined || value === "") {
    return '<span class="muted">Not provided</span>';
  }
  if (typeof value === "number") {
    return `<span>${formatNumber(value)}</span>`;
  }
  if (typeof value === "boolean") {
    return `<span>${value ? "Yes" : "No"}</span>`;
  }
  const textSegments = String(value)
    .split(/\r?\n+/)
    .map((line) => `<p class="result-paragraph">${escapeHtml(line)}</p>`)
    .join("");
  return textSegments || '<span class="muted">Not provided</span>';
}

function renderObject(obj, depth) {
  const entries = Object.entries(obj || {});
  if (!entries.length) {
    return '<span class="muted">No details available</span>';
  }
  const rows = entries.map(([key, val]) => {
    const content = renderData(val, depth + 1);
    return `
      <div class="kv-row">
        <span class="kv-key">${escapeHtml(prettifyKey(key))}</span>
        <div class="kv-value">${content}</div>
      </div>
    `;
  });
  return `<div class="kv-grid">${rows.join("")}</div>`;
}

function renderArray(list, depth) {
  if (!list.length) {
    return '<span class="muted">No items</span>';
  }
  const capped = list.slice(0, MAX_LIST_ITEMS);
  const remaining = list.length - capped.length;
  if (capped.every((item) => item && typeof item === "object" && !Array.isArray(item))) {
    const cards = capped.map((item, index) => `
      <div class="stack-item">
        <span class="stack-index">${index + 1}</span>
        <div class="stack-content">${renderObject(item, depth + 1)}</div>
      </div>
    `);
    const more = remaining > 0 ? `<p class="muted">+ ${remaining} more not shown</p>` : "";
    return `<div class="stack">${cards.join("")}${more}</div>`;
  }
  const values = capped.map((item, index) => `
    <div class="list-item">
      <span class="list-index">${index + 1}</span>
      <div class="list-value">${renderScalar(item)}</div>
    </div>
  `);
  const more = remaining > 0 ? `<p class="muted">+ ${remaining} more not shown</p>` : "";
  return `<div class="list">${values.join("")}${more}</div>`;
}

function renderData(value, depth = 0) {
  if (value === null || value === undefined || value === "") {
    return '<span class="muted">No data available</span>';
  }
  if (Array.isArray(value)) {
    return renderArray(value, depth);
  }
  if (typeof value === "object") {
    return renderObject(value, depth);
  }
  return renderScalar(value);
}

function setPanelState(el, state, content) {
  if (!el) return;
  el.dataset.state = state || "";
  el.innerHTML = content || "";
}

function showLoading(el, label) {
  setPanelState(
    el,
    "loading",
    `
      <p class="result-heading">Loading</p>
      <p class="muted">${escapeHtml(label || "Please wait...")}</p>
    `
  );
}

function showError(el, error) {
  const message = typeof error === "string" ? error : error?.message || "Something went wrong.";
  setPanelState(
    el,
    "error",
    `
      <p class="result-heading result-heading--error">Request failed</p>
      <p>${escapeHtml(message)}</p>
    `
  );
}

function showSuccess(el, data, title = "Results") {
  setPanelState(
    el,
    "ready",
    `
      <p class="result-heading">${escapeHtml(title)}</p>
      ${renderData(data)}
    `
  );
}

function renderStrategyResult(result) {
  if (!result || typeof result !== "object") {
    return '<p class="muted">Strategy data is unavailable.</p>';
  }

  const per = Array.isArray(result.per_ticker) ? result.per_ticker : [];
  const sections = per.map((entry, index) => {
    const tickerLabel = escapeHtml(entry?.ticker || `Ticker ${index + 1}`);
    const orderLabel = escapeHtml(`Ticker ${index + 1}`);

    const subsections = [
      { label: "Fundamentals", value: entry?.fundamentals },
      { label: "Street", value: entry?.street },
      { label: "News", value: entry?.news },
      { label: "Signals", value: entry?.signals },
    ].map(({ label, value }) => {
      return `
        <details class="strategy-subsection">
          <summary>${escapeHtml(label)}</summary>
          <div class="strategy-subsection__body">${renderData(value)}</div>
        </details>
      `;
    }).join("");

    return `
      <details class="strategy-card">
        <summary>${orderLabel}: ${tickerLabel}</summary>
        <div class="strategy-card__body">
          ${subsections}
        </div>
      </details>
    `;
  }).join("");

  const allocationBlock = (() => {
    const allocation = result?.allocation || {};
    const rationale = result?.rationale;
    if (!Object.keys(allocation).length && !rationale) {
      return "";
    }
    return `
      <details class="strategy-card">
        <summary>Allocation Plan</summary>
        <div class="strategy-card__body strategy-card__body--allocation">
          <div class="strategy-allocation">
            <div>
              <h4>Allocation</h4>
              ${renderData(allocation)}
            </div>
            <div>
              <h4>Rationale</h4>
              ${renderScalar(rationale)}
            </div>
          </div>
        </div>
      </details>
    `;
  })();

  const disclaimer = result?.disclaimer
    ? `<p class="muted strategy-disclaimer">${escapeHtml(result.disclaimer)}</p>`
    : "";

  return `
    <div class="strategy-list">
      ${sections || '<p class="muted">No tickers returned.</p>'}
      ${allocationBlock}
      ${disclaimer}
    </div>
  `;
}

function showStrategy(el, result) {
  const tickers = Array.isArray(result?.tickers) ? result.tickers : [];
  const tickerLine = tickers.length
    ? `<p class="muted">Tickers: ${escapeHtml(tickers.join(", "))}</p>`
    : "";
  const riskLine = typeof result?.risk !== "undefined"
    ? `<p class="muted">Risk level ${escapeHtml(String(result.risk))} (1=conservative, 5=aggressive)</p>`
    : "";

  setPanelState(
    el,
    "ready",
    `
      <p class="result-heading">Strategy outline</p>
      ${riskLine}
      ${tickerLine}
      ${renderStrategyResult(result)}
    `
  );
}

function clearPanel(el) {
  if (!el) return;
  setPanelState(el, "", "");
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, { cache: "no-store", ...options });
  const text = await res.text();
  let data = null;

  if (text) {
    try {
      data = JSON.parse(text);
    } catch (err) {
      data = null;
    }
  }

  if (!res.ok) {
    const detail = data && data.detail ? data.detail : text || res.statusText;
    throw new Error(detail.trim() || `Request failed with status ${res.status}`);
  }

  if (data !== null) {
    return data;
  }

  if (!text) {
    return {};
  }

  return { message: text };
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
    empty.className = "news-item news-item--empty";
    empty.textContent = "Headlines will appear here once loaded.";
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
    textWrap.className = "news-item__text";

    const headline = document.createElement("div");
    headline.className = "news-item__headline";
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
        /* Ignore date parsing issues */
      }
    }
    if (item.source) {
      metaParts.push(item.source);
    }
    if (metaParts.length) {
      const meta = document.createElement("div");
      meta.className = "news-item__meta";
      meta.textContent = metaParts.join(" � ");
      textWrap.appendChild(meta);
    }

    if (item.summary) {
      const summary = document.createElement("div");
      summary.className = "news-item__summary";
      summary.textContent = item.summary;
      textWrap.appendChild(summary);
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

document.getElementById("btnHealth").addEventListener("click", async () => {
  showLoading(panels.health, "Checking service health");
  try {
    const data = await fetchJson("/health");
    showSuccess(panels.health, data, "Service health");
  } catch (err) {
    showError(panels.health, err);
  }
});

document.getElementById("btnDb").addEventListener("click", async () => {
  showLoading(panels.db, "Pinging database");
  try {
    const data = await fetchJson("/db/ping");
    showSuccess(panels.db, data, "Database response");
  } catch (err) {
    showError(panels.db, err);
  }
});

document.getElementById("btnAsset").addEventListener("click", async () => {
  const ticker = getInputValue("assetTicker");
  if (!ticker) {
    showError(panels.asset, "Enter a ticker to look up.");
    return;
  }
  showLoading(panels.asset, `Fetching ${ticker.toUpperCase()}`);
  try {
    const data = await fetchJson(`/asset/${encodeURIComponent(ticker)}`);
    showSuccess(panels.asset, data, `${ticker.toUpperCase()} details`);
  } catch (err) {
    showError(panels.asset, err);
  }
});

document.getElementById("btnIngest").addEventListener("click", async () => {
  const tickers = parseTickerList(getInputValue("ingestTickers"));
  if (!tickers.length) {
    showError(panels.ingest, "Enter 1-50 tickers to ingest.");
    return;
  }
  const include = document.getElementById("includeMetrics").checked ? "&include=metrics" : "";
  const qsTickers = tickers.map((t) => `tickers=${encodeURIComponent(t)}`).join("&");
  const url = `/ingest/finnhub?${qsTickers}${include}`;
  showLoading(panels.ingest, `Ingesting ${tickers.length} tickers`);
  try {
    const data = await fetchJson(url);
    showSuccess(panels.ingest, data, "Ingest summary");
  } catch (err) {
    showError(panels.ingest, err);
  }
});

document.getElementById("btnFund").addEventListener("click", async () => {
  const ticker = getInputValue("anTicker");
  if (!ticker) {
    showError(panels.fund, "Enter a ticker to analyze fundamentals.");
    return;
  }
  const url = `/analyze/fundamentals_v1?ticker=${encodeURIComponent(ticker)}`;
  showLoading(panels.fund, `Analyzing fundamentals for ${ticker.toUpperCase()}`);
  try {
    const data = await fetchJson(url);
    showSuccess(panels.fund, data, `${ticker.toUpperCase()} fundamentals`);
  } catch (err) {
    showError(panels.fund, err);
  }
});

document.getElementById("btnStreet").addEventListener("click", async () => {
  const ticker = getInputValue("anTicker");
  if (!ticker) {
    showError(panels.street, "Enter a ticker to view analyst sentiment.");
    return;
  }
  const url = `/analyze/street?ticker=${encodeURIComponent(ticker)}`;
  showLoading(panels.street, `Fetching street view for ${ticker.toUpperCase()}`);
  try {
    const data = await fetchJson(url);
    showSuccess(panels.street, data, `${ticker.toUpperCase()} street view`);
  } catch (err) {
    showError(panels.street, err);
  }
});

document.getElementById("btnNewsLoad").addEventListener("click", async () => {
  const ticker = getInputValue("newsTicker");
  const days = Number(document.getElementById("newsDays").value || 30);
  const limit = Number(document.getElementById("newsLimit").value || 8);
  if (!ticker) {
    showError(panels.news, "Enter a ticker to load headlines.");
    return;
  }

  const url = `/finnhub/news/${encodeURIComponent(ticker)}?days=${encodeURIComponent(days)}&limit=${encodeURIComponent(limit)}`;
  showLoading(panels.news, `Loading headlines for ${ticker.toUpperCase()}`);
  newsState.ticker = ticker;
  newsState.items = [];
  renderNewsList([]);
  try {
    const data = await fetchJson(url);
    const items = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
    newsState.items = items.slice(0, limit);
    renderNewsList(newsState.items);
    showSuccess(panels.news, { ticker: ticker.toUpperCase(), headlinesLoaded: newsState.items.length }, "News overview");
  } catch (err) {
    showError(panels.news, err);
  }
});

document.getElementById("btnNewsSummarize").addEventListener("click", async () => {
  const ticker = newsState.ticker;
  const headlines = selectedHeadlines();
  if (!ticker) {
    showError(panels.news, "Load news before summarizing.");
    return;
  }
  if (!headlines.length) {
    showError(panels.news, "Select at least one headline to summarize.");
    return;
  }

  showLoading(panels.news, "Summarizing selected headlines");
  try {
    const payload = { ticker, headlines };
    const data = await fetchJson("/analyze/news_refine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    showSuccess(panels.news, data, "Headline summary");
  } catch (err) {
    showError(panels.news, err);
  }
});

document.getElementById("btnAdvice").addEventListener("click", async () => {
  const tickers = parseTickerList(getInputValue("adviceTickers")).slice(0, 10);
  const riskRaw = Number(document.getElementById("adviceRisk").value || 3);
  const risk = Number.isFinite(riskRaw) ? Math.min(5, Math.max(1, Math.round(riskRaw))) : 3;
  if (!tickers.length) {
    showError(panels.advice, "Enter at least one ticker for advice.");
    return;
  }
  showLoading(panels.advice, "Generating educational strategy");
  try {
    const data = await fetchJson("/advice/v1", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers, risk }),
    });
    showStrategy(panels.advice, data);
  } catch (err) {
    showError(panels.advice, err);
  }
});

renderNewsList([]);
