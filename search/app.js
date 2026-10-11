/**
 * app.js — Sri Valmiki Ramayana Search UI
 *
 * Features:
 *  - Verse reference lookup (1.1.1 → direct fetch; 1.1.19 → finds combined 19-20)
 *  - Full-text search via FTS5 API
 *  - Kanda filter, field toggles
 *  - Modal verse detail with collapsible commentary
 *  - Keyboard shortcuts (Esc to close, / to focus search)
 */

const API = "http://localhost:5000";

/* ── State ───────────────────────────────────────────── */
const state = {
  query: "",
  kanda: "",
  offset: 0,
  limit: 30,
  results: [],
  loading: false,
  activeFields: new Set(["translation", "commentary", "sanskrit"]),
  currentVerse: null,
};

/* ── DOM refs ────────────────────────────────────────── */
const $ = id => document.getElementById(id);
const searchInput   = $("searchInput");
const searchClear   = $("searchClear");
const filterKanda   = $("filterKanda");
const loadingWrap   = $("loadingWrap");
const errorWrap     = $("errorWrap");
const errorMsg      = $("errorMsg");
const resultsList   = $("resultsList");
const resultsHeader = $("resultsHeader");
const resultsCount  = $("resultsCount");
const welcomeState  = $("welcomeState");
const loadMoreWrap  = $("loadMoreWrap");
const loadMoreBtn   = $("loadMoreBtn");
const kandaGrid     = $("kandaGrid");
const modalOverlay  = $("modalOverlay");
const modalClose    = $("modalClose");
const modalBody     = $("modalBody");
const statVerses    = $("statVerses");

/* ── Utilities ───────────────────────────────────────── */
function debounce(fn, delay) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
}

/** Detect if query is a verse reference like 1.1.1 or 1.1.19-20 */
function parseVerseRef(q) {
  const trimmed = q.trim();
  const m = trimmed.match(/^(\d+)\.(\d+)\.(\d+(?:-\d+)?)$/);
  if (!m) return null;
  return { kanda: parseInt(m[1]), chapter: parseInt(m[2]), verse: m[3] };
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function truncate(str, n) {
  if (!str || str.length <= n) return str;
  return str.slice(0, n).trimEnd() + "…";
}

function show(el) { el.style.display = ""; }
function hide(el) { el.style.display = "none"; }

/* ── API calls ───────────────────────────────────────── */
async function apiFetch(path) {
  const res = await fetch(API + path);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

async function fetchVerseByRef(ref) {
  return apiFetch(`/verse/${ref}`);
}

async function fetchSearch(q, kanda, offset, limit) {
  let url = `/search?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`;
  if (kanda) url += `&kanda=${kanda}`;
  return apiFetch(url);
}

async function fetchStats() {
  return apiFetch("/stats");
}

async function fetchKandas() {
  return apiFetch("/kandas");
}

/* ── Render helpers ──────────────────────────────────── */
function renderVerseCard(verse, highlight = "") {
  const ref         = escapeHtml(verse.verse_ref || "");
  const kanda       = escapeHtml(verse.kanda_name || "");
  const chapter     = escapeHtml(verse.chapter_title || "");
  const sanskrit    = escapeHtml(verse.sanskrit || "");
  const iast        = escapeHtml(verse.transliteration || "");
  const translation = escapeHtml(verse.translation || "");
  const snippet     = verse.matched_snippet || "";

  const showSkt  = state.activeFields.has("sanskrit");
  const showTrans = state.activeFields.has("translation");
  const showComm = state.activeFields.has("commentary");

  let body = "";

  if (showSkt && sanskrit) {
    body += `<div class="verse-sanskrit">${sanskrit}</div>`;
  }

  if (iast) {
    body += `<div class="verse-iast">${iast}</div>`;
  }

  if (showTrans && translation) {
    body += `<div class="verse-translation">${translation}</div>`;
  }

  if (showComm && snippet && !snippet.includes(translation.slice(0, 30))) {
    body += `<div class="verse-snippet">${snippet}</div>`;
  }

  return `
    <div class="verse-card" data-ref="${ref}" role="button" tabindex="0"
         aria-label="Verse ${ref}">
      <div class="verse-card-header">
        <div class="verse-ref-badge">
          <span>📜</span> ${ref}
        </div>
        <div class="verse-meta">
          ${kanda}<br>
          <span style="font-size:.75em">${chapter}</span>
        </div>
      </div>
      ${body}
      <div class="card-actions">
        <button class="card-btn primary" onclick="openVerseModal('${ref}', event)">Full verse + commentary</button>
        <button class="card-btn" onclick="copyRef('${ref}', event)">Copy ref</button>
        <a class="card-btn" href="${escapeHtml(verse.url || '')}" target="_blank" rel="noopener"
           onclick="event.stopPropagation()">Source ↗</a>
      </div>
    </div>
  `;
}

function renderFullVerse(verse) {
  const ref         = escapeHtml(verse.verse_ref || "");
  const kanda       = escapeHtml(verse.kanda_name || "");
  const chapter     = escapeHtml(verse.chapter_title || "");
  const sanskrit    = escapeHtml(verse.sanskrit || "");
  const iast        = escapeHtml(verse.transliteration || "");
  const wordmean    = escapeHtml(verse.word_meaning || "");
  const translation = escapeHtml(verse.translation || "");
  const commentary  = verse.commentary || "";
  const quotations  = escapeHtml(verse.quotations || "");
  const footnotes   = escapeHtml(verse.footnotes || "");
  const url         = escapeHtml(verse.url || "#");

  const hasComm = commentary.trim().length > 0;
  const commId  = "comm_" + Math.random().toString(36).slice(2);

  return `
    <div class="fv-header">
      <div class="fv-ref">📜 Text ${ref}</div>
      <div class="fv-kanda">${kanda}</div>
      <div class="fv-chapter">${chapter}</div>
    </div>

    ${sanskrit ? `
    <div class="fv-section">
      <div class="fv-label">Sanskrit · Devanāgarī</div>
      <div class="fv-sanskrit">${sanskrit}</div>
    </div>` : ""}

    ${iast ? `
    <div class="fv-section">
      <div class="fv-label">Transliteration · IAST</div>
      <div class="fv-iast">${iast}</div>
    </div>` : ""}

    ${wordmean ? `
    <div class="fv-section">
      <div class="fv-label">Word-by-Word Meaning</div>
      <div class="fv-wordbyword">${wordmean}</div>
    </div>` : ""}

    ${translation ? `
    <div class="fv-section">
      <div class="fv-label">English Translation</div>
      <div class="fv-translation">${translation}</div>
    </div>` : ""}

    ${hasComm ? `
    <div class="fv-section">
      <div class="fv-label">Commentary</div>
      <div class="commentary-wrap">
        <div class="fv-commentary commentary-collapsed" id="${commId}">
          ${escapeHtml(commentary)}
        </div>
        <button class="btn-expand" onclick="toggleCommentary('${commId}', this)">
          ▼ Read full commentary
        </button>
      </div>
    </div>` : ""}

    ${quotations ? `
    <div class="fv-section">
      <div class="fv-label">Quotations</div>
      <div class="fv-wordbyword" style="font-size:.82rem">${quotations}</div>
    </div>` : ""}

    ${footnotes ? `
    <div class="fv-section">
      <div class="fv-label">Footnotes</div>
      <div class="fv-wordbyword" style="font-size:.8rem">${footnotes}</div>
    </div>` : ""}

    <div class="fv-source">
      Source: <a href="${url}" target="_blank" rel="noopener">${url}</a>
    </div>

    <div class="fv-nav">
      <button class="fv-nav-btn" onclick="navigateVerse('${ref}', -1)">← Previous</button>
      <button class="fv-nav-btn" onclick="navigateVerse('${ref}', 1)">Next →</button>
    </div>
  `;
}

function renderKandaCards(kandas) {
  if (!kandas || kandas.length === 0) {
    kandaGrid.innerHTML = `<p style="color:var(--text-muted); font-size:.85rem; grid-column:1/-1">
      No data yet. Run the scraper first: <code>python scraper/scrape.py --kanda 1</code></p>`;
    return;
  }
  kandaGrid.innerHTML = kandas.map(k => `
    <div class="kanda-card" onclick="browseKanda(${k.kanda_num})" role="button" tabindex="0">
      <div class="kanda-num">Kāṇḍa ${k.kanda_num}</div>
      <div class="kanda-name">${escapeHtml(k.kanda_name)}</div>
      <div class="kanda-count">${k.verse_count} verses · ${k.chapter_count} chapters</div>
    </div>
  `).join("");
}

/* ── Main search flow ────────────────────────────────── */
async function runSearch(append = false) {
  const q     = state.query.trim();
  const kanda = state.kanda;

  if (!q) {
    showWelcome();
    return;
  }

  // Check if it's a verse reference
  const ref = parseVerseRef(q);
  if (ref) {
    await lookupVerse(`${ref.kanda}.${ref.chapter}.${ref.verse}`);
    return;
  }

  // Full-text search
  if (!append) {
    state.offset  = 0;
    state.results = [];
    resultsList.innerHTML = "";
  }

  state.loading = true;
  hideWelcome();
  if (!append) {
    show(loadingWrap);
    hide(errorWrap);
    hide(resultsHeader);
    hide(loadMoreWrap);
  }

  try {
    const data = await fetchSearch(q, kanda, state.offset, state.limit);
    const rows = data.results || [];

    if (!append) hide(loadingWrap);

    if (rows.length === 0 && !append) {
      resultsCount.textContent = "No results found";
      show(resultsHeader);
      resultsList.innerHTML = `
        <div style="text-align:center; padding:40px 0; color:var(--text-muted)">
          <div style="font-size:2rem; margin-bottom:12px">🔍</div>
          <p>No verses matched "<strong style="color:var(--text-secondary)">${escapeHtml(q)}</strong>"</p>
          <p style="font-size:.82rem; margin-top:8px">Try different keywords or a verse reference like <code>1.1.1</code></p>
        </div>`;
      return;
    }

    state.results.push(...rows);

    if (!append) {
      resultsCount.textContent = `Found ${rows.length < state.limit ? rows.length : "many"} results`;
      show(resultsHeader);
    }

    rows.forEach(v => {
      resultsList.insertAdjacentHTML("beforeend", renderVerseCard(v, q));
    });

    // Attach click handlers to new cards
    attachCardListeners();

    // Show "load more" if we got a full page
    if (rows.length === state.limit) {
      state.offset += state.limit;
      show(loadMoreWrap);
    } else {
      hide(loadMoreWrap);
    }

  } catch (err) {
    hide(loadingWrap);
    errorMsg.textContent = err.message || "Search failed.";
    show(errorWrap);
  }

  state.loading = false;
}

async function lookupVerse(ref) {
  hideWelcome();
  show(loadingWrap);
  hide(errorWrap);
  hide(resultsHeader);
  hide(loadMoreWrap);
  resultsList.innerHTML = "";

  try {
    const verse = await fetchVerseByRef(ref);
    hide(loadingWrap);

    // Show as a single card
    resultsList.insertAdjacentHTML("beforeend", renderVerseCard(verse));
    attachCardListeners();
    show(resultsHeader);
    resultsCount.textContent = `Verse ${verse.verse_ref}`;

    // Auto-open the modal
    openVerseModal(verse.verse_ref);

  } catch (err) {
    hide(loadingWrap);
    errorMsg.textContent = err.message || "Verse not found.";
    show(errorWrap);
  }
}

/* ── Modal ───────────────────────────────────────────── */
async function openVerseModal(ref, event) {
  if (event) event.stopPropagation();

  // Try to use cached data first
  let verse = state.results.find(v => v.verse_ref === ref);

  if (!verse || !verse.translation) {
    try {
      verse = await fetchVerseByRef(ref);
    } catch (err) {
      return;
    }
  }

  state.currentVerse = verse;
  modalBody.innerHTML = renderFullVerse(verse);
  modalOverlay.classList.add("open");
  document.body.style.overflow = "hidden";
}

function closeModal() {
  modalOverlay.classList.remove("open");
  document.body.style.overflow = "";
  state.currentVerse = null;
}

window.openVerseModal = openVerseModal;

window.toggleCommentary = function(id, btn) {
  const el = document.getElementById(id);
  if (!el) return;
  const isCollapsed = el.classList.contains("commentary-collapsed");
  el.classList.toggle("commentary-collapsed", !isCollapsed);
  btn.textContent = isCollapsed ? "▲ Collapse commentary" : "▼ Read full commentary";
};

window.copyRef = function(ref, event) {
  if (event) event.stopPropagation();
  navigator.clipboard.writeText(ref).then(() => {
    const btn = event?.target;
    if (btn) {
      const orig = btn.textContent;
      btn.textContent = "Copied!";
      setTimeout(() => { btn.textContent = orig; }, 1500);
    }
  });
};

/** Navigate to prev/next verse from inside modal */
window.navigateVerse = async function(currentRef, direction) {
  const parts = currentRef.split(".");
  const kanda   = parseInt(parts[0]);
  const chapter = parseInt(parts[1]);
  const verse   = parseInt(parts[2].split("-")[0]);
  const next    = verse + direction;
  if (next < 0) return;
  const nextRef = `${kanda}.${chapter}.${next}`;
  try {
    const v = await fetchVerseByRef(nextRef);
    state.currentVerse = v;
    modalBody.innerHTML = renderFullVerse(v);
  } catch {
    // At boundary — try next chapter
    if (direction > 0) {
      try {
        const v = await fetchVerseByRef(`${kanda}.${chapter + 1}.1`);
        state.currentVerse = v;
        modalBody.innerHTML = renderFullVerse(v);
      } catch { /* end of content */ }
    }
  }
};

window.browseKanda = function(kandaNum) {
  filterKanda.value = String(kandaNum);
  state.kanda = String(kandaNum);
  searchInput.value = "Rama";
  state.query = "Rama";
  show(searchClear);
  runSearch();
};

/* ── Welcome / stats ─────────────────────────────────── */
function showWelcome() {
  show(welcomeState);
  hide(resultsHeader);
  hide(loadMoreWrap);
  hide(loadingWrap);
  hide(errorWrap);
  resultsList.innerHTML = "";
}

function hideWelcome() {
  hide(welcomeState);
}

async function loadWelcomeData() {
  try {
    const [stats, kandasData] = await Promise.all([fetchStats(), fetchKandas()]);
    statVerses.textContent = `${stats.total_verses.toLocaleString()} verses`;
    renderKandaCards(kandasData.kandas);
  } catch {
    renderKandaCards([]);
    statVerses.textContent = "DB not found";
  }
}

/* ── Event listeners ─────────────────────────────────── */
function attachCardListeners() {
  document.querySelectorAll(".verse-card:not([data-bound])").forEach(card => {
    card.setAttribute("data-bound", "1");
    card.addEventListener("click", () => openVerseModal(card.dataset.ref));
    card.addEventListener("keydown", e => {
      if (e.key === "Enter") openVerseModal(card.dataset.ref);
    });
  });
}

const debouncedSearch = debounce(() => runSearch(), 350);

searchInput.addEventListener("input", () => {
  const q = searchInput.value;
  state.query = q;
  searchClear.style.display = q ? "flex" : "none";
  debouncedSearch();
});

searchInput.addEventListener("keydown", e => {
  if (e.key === "Enter") { clearTimeout(); runSearch(); }
  if (e.key === "Escape") { searchInput.value = ""; state.query = ""; searchClear.style.display = "none"; showWelcome(); }
});

searchClear.addEventListener("click", () => {
  searchInput.value = "";
  state.query = "";
  searchClear.style.display = "none";
  showWelcome();
  searchInput.focus();
});

filterKanda.addEventListener("change", () => {
  state.kanda = filterKanda.value;
  if (state.query) runSearch();
});

document.querySelectorAll(".field-toggle").forEach(btn => {
  btn.addEventListener("click", () => {
    const field = btn.dataset.field;
    if (state.activeFields.has(field)) {
      state.activeFields.delete(field);
      btn.classList.remove("active");
    } else {
      state.activeFields.add(field);
      btn.classList.add("active");
    }
    if (state.query && !parseVerseRef(state.query)) runSearch();
  });
});

loadMoreBtn.addEventListener("click", () => runSearch(true));

modalClose.addEventListener("click", closeModal);
modalOverlay.addEventListener("click", e => {
  if (e.target === modalOverlay) closeModal();
});

// Hint links
document.querySelectorAll(".hint-link, .hint-query").forEach(el => {
  el.addEventListener("click", e => {
    e.preventDefault();
    const q = el.dataset.query;
    searchInput.value = q;
    state.query = q;
    searchClear.style.display = "flex";
    runSearch();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
});

document.querySelectorAll(".hint-ref").forEach(el => {
  el.addEventListener("click", e => {
    e.preventDefault();
    const ref = el.dataset.ref;
    searchInput.value = ref;
    state.query = ref;
    searchClear.style.display = "flex";
    lookupVerse(ref);
  });
});

// Keyboard shortcut: / to focus search
document.addEventListener("keydown", e => {
  if (e.key === "/" && document.activeElement !== searchInput) {
    e.preventDefault();
    searchInput.focus();
    searchInput.select();
  }
  if (e.key === "Escape") closeModal();
});

/* ── Init ────────────────────────────────────────────── */
loadWelcomeData();
showWelcome();
searchInput.focus();
