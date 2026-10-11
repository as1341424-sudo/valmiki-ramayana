"""
build_offline.py  —  Build a single standalone offline HTML app.
Run: python build_offline.py
Open: offline/ramayana.html  (just double-click it)
"""
import sqlite3, json, re, sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB   = Path("data/ramayana.db")
OUT  = Path("offline/ramayana.html")
Path("offline").mkdir(exist_ok=True)

if not DB.exists():
    sys.exit("ERROR: data/ramayana.db not found. Run the scraper first.")

# ── 1. Load data ──────────────────────────────────────────────────
import base64
LOGO_B64 = ""
LOGO_PATH = Path("offline/iskcon_logo.jpg")
if LOGO_PATH.exists():
    with open(LOGO_PATH, "rb") as f:
        LOGO_B64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("utf-8")

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
print("Reading database…")
rows = conn.execute(
    "SELECT * FROM verses ORDER BY kanda_num, chapter_num, verse_num_start"
).fetchall()

verses = []
for r in rows:
    d = dict(r)
    verses.append({
        "id":    d["id"],
        "kn":    d["kanda_num"],
        "kname": d["kanda_name"] or "",
        "cn":    d["chapter_num"],
        "ctitle":d["chapter_title"] or "",
        "ref":   d["verse_ref"] or "",
        "vs":    d["verse_num_start"],
        "ve":    d["verse_num_end"],
        "skt":   d["sanskrit"] or "",
        "iast":  d["transliteration"] or "",
        "wm":    d["word_meaning"] or "",
        "tr":    d["translation"] or "",
        "comm":  d["commentary"] or "",
        "url":   d["url"] or "",
    })
conn.close()
print(f"   {len(verses):,} verses")

# ── 2. Build inverted index ───────────────────────────────────────
print("Building search index…")
TOK_RE = re.compile(r"[a-z\u0101\u012b\u016b\u1e5b\u1e5d\u1e37\u0113\u014d\u1e43\u1e25\xf1\u1e6d\u1e0d\u1e47\u015b\u1e63\u1e41]+")

def tokenize(text):
    return {w[:20] for w in TOK_RE.findall((text or "").lower()) if len(w) >= 3}

inv = {}
for i, v in enumerate(verses):
    text = " ".join([v["tr"], v["comm"], v["skt"], v["iast"], v["wm"], v["ctitle"], v["kname"]])
    for tok in tokenize(text):
        inv.setdefault(tok, []).append(i)

print(f"   {len(inv):,} tokens")

# ── 3. Stats ──────────────────────────────────────────────────────
ks = {}
for v in verses:
    k = str(v["kn"])
    if k not in ks:
        ks[k] = {"name": v["kname"], "verses": 0, "chapters": set()}
    ks[k]["verses"] += 1
    ks[k]["chapters"].add(v["cn"])
for k in ks:
    ks[k]["chapters"] = len(ks[k]["chapters"])

stats = {"total": len(verses), "kandas": ks, "date": datetime.utcnow().strftime("%Y-%m-%d")}

DATA_JSON = json.dumps({"verses": verses, "inv": inv, "stats": stats},
                        ensure_ascii=False, separators=(",", ":"))

N    = len(verses)
DATE = datetime.utcnow().strftime("%Y-%m-%d")

# ── 4. Write HTML (NO f-string — use format() to avoid JS-brace conflicts) ──
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sri Valmiki Ramayana - Offline ({N} verses)</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#faf7f2;--bg2:#f2ece0;--white:#fff;
  --bd:#ddd0b8;--bd2:#c9b898;
  --t:#1e1608;--t2:#5a4a30;--t3:#8c7654;
  --sf:#b85a10;--sf2:#d97030;--lnk:#7a3a08;
  --sh:0 1px 3px rgba(0,0,0,.08);--sh2:0 4px 20px rgba(0,0,0,.14);
  --r:8px;
  --fs:Georgia,"Times New Roman",serif;
  --fu:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --fd:"Noto Serif Devanagari","Mangal",serif;
}}
html{{font-size:16px;scroll-behavior:smooth}}
body{{background:var(--bg);color:var(--t);font-family:var(--fs);line-height:1.7;min-height:100vh}}
a{{color:var(--lnk)}}
a:hover{{text-decoration:underline}}
.hide{{display:none!important}}
.wrap{{max-width:860px;margin:0 auto;padding:0 18px}}

/* --- Header --- */
.hdr{{background:var(--white);border-bottom:2px solid var(--sf);
  position:sticky;top:0;z-index:100;box-shadow:var(--sh)}}
.hdr-in{{max-width:860px;margin:0 auto;padding:10px 18px;
  display:flex;align-items:center;justify-content:space-between;gap:12px}}
.bwrap{{display:flex;align-items:center;gap:10px}}
.blogo{{height:44px;width:auto;display:block;flex-shrink:0}}
.bd{{font-family:var(--fd);font-size:1.15rem;color:var(--sf);line-height:1.2}}
.be{{font-family:var(--fu);font-size:.65rem;color:var(--t3);letter-spacing:.04em}}
.pill{{font-family:var(--fu);font-size:.68rem;background:var(--bg2);
  border:1px solid var(--bd);color:var(--t2);padding:3px 10px;border-radius:20px;white-space:nowrap}}

/* --- Search --- */
.sb{{background:var(--white);border-bottom:1px solid var(--bd);padding:16px 0 12px}}
.sr{{display:flex;gap:8px}}
.sf{{flex:1;display:flex;align-items:center;background:var(--bg);
  border:1.5px solid var(--bd);border-radius:var(--r);padding:0 12px;
  transition:border-color .18s,background .18s}}
.sf:focus-within{{border-color:var(--sf);background:var(--white)}}
.ico{{color:var(--t3);margin-right:8px;line-height:0;flex-shrink:0}}
.si{{flex:1;border:none;background:transparent;font-family:var(--fs);
  font-size:.95rem;color:var(--t);padding:10px 0;outline:none}}
.si::placeholder{{color:var(--t3)}}
.xbtn{{background:none;border:none;cursor:pointer;line-height:0;color:var(--t3);
  padding:4px;border-radius:4px;flex-shrink:0}}
.xbtn:hover{{background:var(--bg2);color:var(--t)}}
.frow{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;
  margin-top:10px;font-family:var(--fu);font-size:.75rem;color:var(--t3)}}
.sel{{font-family:var(--fu);font-size:.78rem;background:var(--bg);
  border:1px solid var(--bd);border-radius:6px;padding:5px 10px;color:var(--t);cursor:pointer}}
.sel:focus{{outline:none;border-color:var(--sf)}}
.lbl{{display:flex;align-items:center;gap:4px;cursor:pointer;color:var(--t2)}}
.lbl input{{accent-color:var(--sf)}}
.hints{{margin-top:9px;font-family:var(--fu);font-size:.75rem;color:var(--t3)}}
.hl{{color:var(--lnk);cursor:pointer;text-decoration:underline;text-underline-offset:2px}}

/* --- Main --- */
.main{{padding:24px 0 70px}}
.strow{{display:flex;align-items:center;gap:8px;
  font-family:var(--fu);font-size:.8rem;color:var(--t3);margin-bottom:14px}}
.spin{{width:14px;height:14px;border-radius:50%;
  border:2px solid var(--bd);border-top-color:var(--sf);
  animation:sp .7s linear infinite;flex-shrink:0}}
@keyframes sp{{to{{transform:rotate(360deg)}}}}
.rmeta{{font-family:var(--fu);font-size:.75rem;color:var(--t3);margin-bottom:12px}}
.rmeta strong{{color:var(--t2)}}

/* --- Welcome --- */
.wh{{font-family:var(--fu);font-size:.7rem;text-transform:uppercase;
  letter-spacing:.09em;color:var(--t3);margin-bottom:12px}}
.kg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));
  gap:10px;margin-bottom:28px}}
.kc{{background:var(--white);border:1px solid var(--bd);border-radius:var(--r);
  padding:14px 16px;cursor:pointer;transition:border-color .15s,box-shadow .15s}}
.kc:hover{{border-color:var(--sf2);box-shadow:var(--sh)}}
.knum{{font-family:var(--fu);font-size:.65rem;color:var(--t3);margin-bottom:3px}}
.kname{{font-size:.9rem;font-weight:700;color:var(--sf);margin-bottom:5px}}
.kmeta{{font-family:var(--fu);font-size:.68rem;color:var(--t3)}}
.tg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}}
.tc{{background:var(--white);border:1px solid var(--bd);border-radius:var(--r);padding:14px 16px}}
.tico{{font-size:1.1rem;margin-bottom:5px}}
.tt{{font-size:.85rem;font-weight:700;color:var(--t);margin-bottom:4px}}
.tb{{font-family:var(--fu);font-size:.73rem;color:var(--t2);line-height:1.55}}
.tb code{{background:var(--bg2);border-radius:3px;padding:0 4px;font-size:.75rem}}

/* --- Result cards --- */
.rc{{background:var(--white);border:1px solid var(--bd);border-radius:var(--r);
  padding:16px 18px;margin-bottom:8px;cursor:pointer;
  transition:border-color .15s,box-shadow .15s}}
.rc:hover{{border-color:var(--sf2);box-shadow:var(--sh)}}
.rc:focus{{outline:2px solid var(--sf);outline-offset:2px}}
.rm{{display:flex;align-items:center;flex-wrap:wrap;gap:6px;
  font-family:var(--fu);font-size:.68rem;color:var(--t3);margin-bottom:7px}}
.rref{{font-weight:700;color:var(--sf);font-size:.72rem}}
.rskt{{font-family:var(--fd);font-size:.95rem;color:var(--t2);margin-bottom:6px;line-height:1.75;text-align:center;white-space:pre-line}}
.riast{{font-style:italic;font-size:.82rem;color:var(--t3);margin-bottom:7px;text-align:center;white-space:pre-line}}
.rtrans{{font-size:.88rem;color:var(--t);line-height:1.6}}
mark{{background:#ffe97a;color:inherit;border-radius:2px;padding:0 1px}}
.lmw{{text-align:center;margin-top:18px}}
.lmbtn{{font-family:var(--fu);font-size:.8rem;background:var(--white);
  border:1.5px solid var(--bd);border-radius:6px;padding:8px 24px;
  cursor:pointer;color:var(--t2);transition:border-color .15s}}
.lmbtn:hover{{border-color:var(--sf);color:var(--t)}}

/* --- Modal --- */
.bkd{{display:none;position:fixed;inset:0;background:rgba(20,12,0,.45);z-index:200;
  align-items:flex-start;justify-content:center;padding:20px 16px;overflow-y:auto}}
.bkd.open{{display:flex}}
.modal{{background:var(--white);border:1px solid var(--bd);border-radius:12px;
  width:100%;max-width:720px;margin:auto;padding:26px;
  position:relative;box-shadow:var(--sh2)}}
.mcls{{position:absolute;top:12px;right:12px;background:none;border:none;cursor:pointer;
  color:var(--t3);padding:5px;line-height:0;border-radius:5px}}
.mcls:hover{{background:var(--bg2);color:var(--t)}}
.mcrumb{{font-family:var(--fu);font-size:.68rem;color:var(--t3);margin-bottom:3px}}
.mcrumb a{{color:var(--sf2)}}
.mref{{font-size:1.05rem;font-weight:700;color:var(--sf);margin-bottom:14px}}
.sl{{font-family:var(--fu);font-size:.62rem;text-transform:uppercase;letter-spacing:.1em;
  color:var(--t3);display:flex;align-items:center;gap:6px;margin:15px 0 5px}}
.sl::after{{content:"";flex:1;height:1px;background:var(--bd)}}
.vskt{{font-family:var(--fd);font-size:1.15rem;line-height:2.1;color:var(--t);text-align:center;white-space:pre-line;background:var(--bg);border:1px solid var(--bd);border-radius:var(--r);padding:14px 18px;margin:8px 0}}
.viast{{font-style:italic;font-size:.9rem;line-height:1.9;color:var(--t2);text-align:center;white-space:pre-line;margin:6px 0 10px}}
.vwm,.vtrans{{font-size:.9rem;line-height:1.7;color:var(--t)}}
.vcomm{{font-size:.83rem;line-height:1.85;color:var(--t2);white-space:pre-wrap;
  max-height:280px;overflow-y:auto;background:var(--bg);border:1px solid var(--bd);
  border-radius:6px;padding:10px 14px}}
.vcomm::-webkit-scrollbar{{width:5px}}
.vcomm::-webkit-scrollbar-thumb{{background:var(--bd2);border-radius:3px}}
.mnav{{display:flex;gap:8px;justify-content:space-between;
  margin-top:20px;padding-top:14px;border-top:1px solid var(--bd)}}
.bnav{{font-family:var(--fu);font-size:.75rem;background:var(--bg);
  border:1px solid var(--bd);border-radius:6px;padding:7px 14px;
  cursor:pointer;color:var(--t2);transition:border-color .15s}}
.bnav:hover{{border-color:var(--sf)}}
.bnav:disabled{{opacity:.35;cursor:default;pointer-events:none}}

/* --- Footer --- */
.ftr{{border-top:1px solid var(--bd);padding:16px 0;text-align:center;
  font-family:var(--fu);font-size:.7rem;color:var(--t3)}}
.ftr a{{color:var(--lnk)}}
@media(max-width:520px){{.modal{{padding:14px}}.kg,.tg{{grid-template-columns:1fr 1fr}}}}
@media(max-width:360px){{.kg,.tg{{grid-template-columns:1fr}}}}
</style>
</head>
<body>

<header class="hdr">
  <div class="hdr-in">
    <div class="bwrap">
      <img class="blogo" src="LOGO_SRC_PLACEHOLDER" alt="ISKCON Lotus Logo">
      <div>
        <div class="bd">&#x936;&#x94d;&#x930;&#x940;&#x935;&#x93e;&#x932;&#x94d;&#x92e;&#x940;&#x915;&#x93f;&#x930;&#x93e;&#x92e;&#x93e;&#x92f;&#x923;&#x92e;&#x94d;</div>
        <div class="be">&#x15a;r&#x12b; V&#x101;lm&#x12b;ki R&#x101;m&#x101;ya&#x1e47;a &middot; Offline Edition</div>
      </div>
    </div>
    <span class="pill" id="badge">Loading&hellip;</span>
  </div>
</header>

<div class="sb">
  <div class="wrap">
    <div class="sr">
      <div class="sf">
        <span class="ico">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
        </span>
        <input class="si" id="q" type="text"
          placeholder="Search (dharma, Narada&hellip;) or verse ref like 1.1.1"
          autocomplete="off" spellcheck="false">
        <button class="xbtn hide" id="xbtn" title="Clear">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="frow">
      <span>Filter:</span>
      <select class="sel" id="fk">
        <option value="">All K&#x101;&#x1e47;&#x1e0d;as</option>
        <option value="1">1 &middot; B&#x101;la-k&#x101;&#x1e47;&#x1e0d;a</option>
        <option value="2">2 &middot; Ayodhy&#x101;-k&#x101;&#x1e47;&#x1e0d;a</option>
        <option value="3">3 &middot; &#x100;ra&#x1e47;ya-k&#x101;&#x1e47;&#x1e0d;a</option>
        <option value="4">4 &middot; Ki&#x1e63;kindh&#x101;-k&#x101;&#x1e47;&#x1e0d;a</option>
        <option value="5">5 &middot; Sundara-k&#x101;&#x1e47;&#x1e0d;a</option>
        <option value="6">6 &middot; Yuddha-k&#x101;&#x1e47;&#x1e0d;a</option>
        <option value="7">7 &middot; Uttara-k&#x101;&#x1e47;&#x1e0d;a</option>
      </select>
      <span>Search in:</span>
      <label class="lbl"><input type="checkbox" id="cSkt" checked> Sanskrit</label>
      <label class="lbl"><input type="checkbox" id="cTr" checked> Translation</label>
      <label class="lbl"><input type="checkbox" id="cCo" checked> Commentary</label>
    </div>
    <div class="hints">
      Try:
      <span class="hl" onclick="setRef('1.1.1')">1.1.1</span> &middot;
      <span class="hl" onclick="setRef('1.2.1')">1.2.1</span> &middot;
      <span class="hl" onclick="setQ('Narada')">Narada</span> &middot;
      <span class="hl" onclick="setQ('Sita')">Sita</span> &middot;
      <span class="hl" onclick="setQ('dharma')">dharma</span> &middot;
      <span class="hl" onclick="setQ('austerity')">austerity</span>
    </div>
  </div>
</div>

<main class="main">
  <div class="wrap">
    <div class="strow hide" id="strow"><div class="spin"></div><span>Searching&hellip;</span></div>
    <div class="rmeta hide" id="rmeta"></div>
    <div id="rlist"></div>
    <div class="lmw hide" id="lmw">
      <button class="lmbtn" onclick="loadMore()">Load more results</button>
    </div>

    <div id="welcome">
      <div class="wh">K&#x101;&#x1e47;&#x1e0d;as in this offline edition</div>
      <div class="kg" id="kg"></div>
      <div class="tg">
        <div class="tc"><div class="tico">&#128214;</div>
          <div class="tt">Verse lookup</div>
          <div class="tb">Type <code>1.1.1</code> to open K&#x101;&#x1e47;&#x1e0d;a 1, Ch. 1, Verse 1.
          Combined verses like <code>1.1.19</code> and <code>1.1.20</code> both open the 19&ndash;20 entry.</div></div>
        <div class="tc"><div class="tico">&#128269;</div>
          <div class="tt">Full-text search</div>
          <div class="tb">Searches Sanskrit, IAST, word meanings, translation &amp; commentary. 100% offline &mdash; no internet needed.</div></div>
        <div class="tc"><div class="tico">&#128218;</div>
          <div class="tt">Browse by K&#x101;&#x1e47;&#x1e0d;a</div>
          <div class="tb">Click any K&#x101;&#x1e47;&#x1e0d;a card above to browse all its verses.</div></div>
        <div class="tc"><div class="tico">&#9000;</div>
          <div class="tt">Keyboard shortcuts</div>
          <div class="tb"><b>&larr; &rarr;</b> navigate &middot; <b>Esc</b> close &middot; <b>Enter</b> search</div></div>
      </div>
    </div>
  </div>
</main>

<div class="bkd" id="bkd">
  <div class="modal">
    <button class="mcls" id="mcls" title="Close (Esc)">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M18 6 6 18M6 6l12 12"/>
      </svg>
    </button>
    <div id="mbody"></div>
    <div class="mnav">
      <button class="bnav" id="bprev">&larr; Previous</button>
      <button class="bnav" id="bnext">Next &rarr;</button>
    </div>
  </div>
</div>

<footer class="ftr">
  <div class="wrap">
    Content from <a href="https://srivalmikiramayana.com" target="_blank" rel="noopener">srivalmikiramayana.com</a>
    &middot; {N} verses &middot; Built {DATE}
  </div>
</footer>

<script>
// ── Inline data ──────────────────────────────────────────────────
var _D = DATA_PLACEHOLDER;
</script>

<script>
// ── App ──────────────────────────────────────────────────────────
var V=_D.verses, IDX=_D.inv, ST=_D.stats;
var res=[], shown=0, mvi=-1, lastQ="", PG=20;

// Kanda names come from the embedded data (already JSON-safe)
var KND = {};
Object.keys(ST.kandas).forEach(function(k){ KND[k] = ST.kandas[k].name; });

function g(id){ return document.getElementById(id); }

// ── Called from inline onclick hints ────────────────────────────
function setQ(q){ g("q").value=q; g("xbtn").classList.remove("hide"); go(q); }
function setRef(r){ g("q").value=r; g("xbtn").classList.remove("hide"); go(r); }

// ── Init ─────────────────────────────────────────────────────────
g("badge").textContent = ST.total.toLocaleString() + " verses";
buildKandas();
setupEvents();

function buildKandas() {
  var grid = g("kg");
  grid.innerHTML = "";
  var keys = Object.keys(ST.kandas).sort(function(a,b){return+a-+b;});
  if (!keys.length) {
    grid.innerHTML = '<p style="color:#8c7654;font-size:.85rem">No verses yet — run the scraper first.</p>';
    return;
  }
  keys.forEach(function(n) {
    var d = ST.kandas[n];
    var div = document.createElement("div");
    div.className = "kc";
    div.innerHTML =
      '<div class="knum">K\u0101\u1e47\u1e0da ' + n + '</div>' +
      '<div class="kname">' + (KND[n] || d.name) + '</div>' +
      '<div class="kmeta">' + d.verses.toLocaleString() + ' verses &middot; ' + d.chapters + ' chapters</div>';
    div.onclick = (function(num){ return function(){
      g("fk").value = num;
      g("q").value = "";
      g("xbtn").classList.add("hide");
      browseKanda(+num);
    }; })(n);
    grid.appendChild(div);
  });
}

function setupEvents() {
  var qEl=g("q"), xbtn=g("xbtn"), fk=g("fk");
  var cSkt=g("cSkt"), cTr=g("cTr"), cCo=g("cCo");

  var tmr;
  qEl.addEventListener("input", function() {
    xbtn.classList.toggle("hide", !qEl.value);
    clearTimeout(tmr);
    tmr = setTimeout(function(){ go(qEl.value.trim()); }, 260);
  });
  qEl.addEventListener("keydown", function(e) {
    if (e.key === "Enter") { clearTimeout(tmr); go(qEl.value.trim()); }
  });
  xbtn.onclick = function() {
    qEl.value = ""; xbtn.classList.add("hide"); qEl.focus(); showWelcome();
  };
  fk.onchange = function() {
    if (qEl.value.trim() || fk.value) go(qEl.value.trim()); else showWelcome();
  };
  [cSkt, cTr, cCo].forEach(function(c) {
    c.onchange = function() { if (g("q").value.trim()) go(g("q").value.trim()); };
  });

  g("mcls").onclick = closeModal;
  g("bkd").onclick = function(e) { if (e.target === g("bkd")) closeModal(); };
  g("bprev").onclick = function() { navModal(-1); };
  g("bnext").onclick = function() { navModal(1); };

  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape") closeModal();
    if (g("bkd").classList.contains("open")) {
      if (e.key === "ArrowLeft")  navModal(-1);
      if (e.key === "ArrowRight") navModal(1);
    }
  });
}

// ── Search ────────────────────────────────────────────────────────
var REF_RE = /^(\d+)\.(\d+)\.(\d+)(?:-\d+)?$/;

function findRef(s) {
  var m = s.match(REF_RE); if (!m) return -1;
  var k=+m[1], c=+m[2], v=+m[3];
  for (var i=0; i<V.length; i++) {
    var x=V[i];
    if (x.kn===k && x.cn===c && x.vs<=v && v<=x.ve) return i;
  }
  return -1;
}

var TOK_PAT = /[a-z\u0101\u012b\u016b\u1e5b\u1e5d\u1e37\u0113\u014d\u1e43\u1e25\xf1\u1e6d\u1e0d\u1e47\u015b\u1e63\u1e41]+/g;
function tokenize(s) {
  var words = ((s||"").toLowerCase().match(TOK_PAT) || []);
  var out = {};
  words.forEach(function(w){ if(w.length>=3) out[w.slice(0,20)]=1; });
  return Object.keys(out);
}

function browseKanda(k) {
  res = [];
  for (var i=0; i<V.length; i++) if (V[i].kn===k) res.push(i);
  showResults("", "Browsing " + (KND[String(k)] || "Kanda "+k));
}

function go(q) {
  lastQ = q;
  if (!q && !g("fk").value) { showWelcome(); return; }
  if (REF_RE.test(q.trim())) {
    var idx = findRef(q.trim());
    if (idx >= 0) { openModal(idx); return; }
  }

  var tokens = tokenize(q);
  var kf = +g("fk").value || 0;
  var qlo = q.toLowerCase().slice(0, 80);
  var hits;

  if (!tokens.length) {
    hits = [];
    for (var i=0; i<V.length; i++) hits.push({i:i, sc:1});
  } else {
    var sm = {};
    tokens.forEach(function(t) {
      (IDX[t]||[]).forEach(function(vi){ sm[vi]=(sm[vi]||0)+2; });
      Object.keys(IDX).forEach(function(k2) {
        if (k2 !== t && k2.indexOf(t) === 0) {
          IDX[k2].forEach(function(vi){ sm[vi]=(sm[vi]||0)+1; });
        }
      });
    });
    hits = Object.keys(sm).map(function(vi){ return {i:+vi, sc:sm[vi]}; });
    hits.sort(function(a,b){ return b.sc-a.sc; });
  }

  var cSkt=g("cSkt").checked, cTr=g("cTr").checked, cCo=g("cCo").checked;
  hits = hits.filter(function(h) {
    var v = V[h.i];
    if (kf && v.kn !== kf) return false;
    if (!tokens.length) return true;
    var fields = [];
    if (cSkt) { fields.push(v.skt); fields.push(v.iast); fields.push(v.wm); }
    if (cTr)  fields.push(v.tr);
    if (cCo)  fields.push(v.comm);
    return fields.some(function(f){ return f && f.toLowerCase().indexOf(qlo) >= 0; });
  });

  res = hits.map(function(h){ return h.i; });
  showResults(q);
}

// ── Render ────────────────────────────────────────────────────────
function showWelcome() {
  g("welcome").classList.remove("hide");
  g("rmeta").classList.add("hide");
  g("rlist").innerHTML = "";
  g("lmw").classList.add("hide");
}

function showResults(q, label) {
  g("welcome").classList.add("hide");
  g("rlist").innerHTML = "";
  shown = 0;
  var n = res.length;
  g("rmeta").classList.remove("hide");
  if (!n) {
    g("rmeta").innerHTML = q ? 'No results for <strong>"' + esc(q) + '"</strong>.' : 'No verses found.';
    g("lmw").classList.add("hide");
    return;
  }
  g("rmeta").innerHTML = label
    ? '<strong>' + n.toLocaleString() + '</strong> verses &mdash; ' + esc(label)
    : '<strong>' + n.toLocaleString() + '</strong> result' + (n!==1?'s':'') + ' for <strong>&ldquo;' + esc(q) + '&rdquo;</strong>';
  loadMore(q);
}

function loadMore(q) {
  if (q === undefined) q = lastQ;
  var end = Math.min(shown + PG, res.length);
  var frag = document.createDocumentFragment();
  for (var i=shown; i<end; i++) frag.appendChild(makeCard(res[i], q));
  g("rlist").appendChild(frag);
  shown = end;
  g("lmw").classList.toggle("hide", shown >= res.length);
}

function makeCard(vi, q) {
  var v = V[vi];
  var card = document.createElement("div");
  card.className = "rc";
  card.tabIndex = 0;

  var skt  = (v.skt  || "").split('\\n')[0].trim();
  var iast = (v.iast || "").split('\\n')[0].trim();
  var tr   = v.tr ? (v.tr.length > 230 ? v.tr.slice(0,230)+"..." : v.tr) : "";
  var ch   = (v.ctitle || "").slice(0, 55);

  var inner = '<div class="rm">'
    + '<span class="rref">' + esc(v.ref) + '</span>'
    + '<span>' + esc(v.kname || "") + ' &middot; Ch.&nbsp;' + v.cn + '</span>'
    + (ch ? '<span>&middot; ' + esc(ch) + '</span>' : '')
    + '</div>';
  if (skt)  inner += '<div class="rskt">'   + hi(esc(skt), q)  + '</div>';
  if (iast) inner += '<div class="riast">'  + hi(esc(iast), q) + '</div>';
  if (tr)   inner += '<div class="rtrans">' + hi(esc(tr), q)   + '</div>';
  card.innerHTML = inner;

  card.onclick = (function(idx){ return function(){ openModal(idx); }; })(vi);
  card.onkeydown = (function(idx){ return function(e){ if(e.key==="Enter") openModal(idx); }; })(vi);
  return card;
}

// ── Modal ─────────────────────────────────────────────────────────
function openModal(vi) {
  mvi = vi;
  renderModal(vi);
  g("bkd").classList.add("open");
  document.body.style.overflow = "hidden";
  g("mcls").focus();
}
function closeModal() {
  g("bkd").classList.remove("open");
  document.body.style.overflow = "";
  mvi = -1;
}
function navModal(d) {
  if (mvi < 0) return;
  var n = mvi + d;
  if (n >= 0 && n < V.length) { mvi = n; renderModal(n); }
}
function renderModal(vi) {
  var v = V[vi], q = lastQ;
  g("bprev").disabled = (vi <= 0);
  g("bnext").disabled = (vi >= V.length - 1);
  var ch = (v.ctitle || "").trim() || "Chapter " + v.cn;
  var html = '<div class="mcrumb">' + esc(v.kname||"") + " &middot; " + esc(ch)
    + (v.url ? ' &middot; <a href="' + esc(v.url) + '" target="_blank" rel="noopener">&#8599; source</a>' : "")
    + '</div><div class="mref">' + esc(v.ref) + '</div>';
  if (v.skt)  html += sec("Sanskrit")              + '<div class="vskt">'   + hi(esc(v.skt),  q) + '</div>';
  if (v.iast) html += sec("Transliteration (IAST)") + '<div class="viast">'  + hi(esc(v.iast), q) + '</div>';
  if (v.wm)   html += sec("Word by word")           + '<div class="vwm">'   + hi(esc(v.wm),   q) + '</div>';
  if (v.tr)   html += sec("Translation")            + '<div class="vtrans">' + hi(esc(v.tr),   q) + '</div>';
  if (v.comm) html += sec("Commentary")             + '<div class="vcomm">'  + hi(esc(v.comm), q) + '</div>';
  g("mbody").innerHTML = html;
  g("mbody").scrollTop = 0;
}
function sec(t) { return '<div class="sl">' + t + '</div>'; }

// ── Helpers ───────────────────────────────────────────────────────
function esc(s) {
  if (!s) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
function hi(html, q) {
  if (!q || q.length < 2) return html;
  var safe = q.replace(/[.*+?^${}()|[\]\\\\]/g, "\\\\$&");
  try { return html.replace(new RegExp("(" + safe + ")", "gi"), "<mark>$1</mark>"); }
  catch(e) { return html; }
}
</script>
</body>
</html>
"""

# Substitute values (after building HTML string, so no brace conflicts)
HTML = HTML.replace("{N}", str(N)).replace("{DATE}", DATE)
HTML = HTML.replace("DATA_PLACEHOLDER", DATA_JSON)
HTML = HTML.replace("LOGO_SRC_PLACEHOLDER", LOGO_B64 or "iskcon_logo.jpg")

# ── 5. Write ──────────────────────────────────────────────────────
print("Writing file…")
with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)

size = OUT.stat().st_size / 1024 / 1024
print(f"\nDone!")
print(f"  File:   {OUT}")
print(f"  Size:   {size:.1f} MB")
print(f"  Verses: {N:,}")
print(f"\n  Double-click  offline/ramayana.html  to open.")
print( "  No server needed. Works 100% offline.")
