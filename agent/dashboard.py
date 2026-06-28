"""누적 코퍼스를 단일 HTML 대시보드로 렌더링한다(독립 실행, 서버 불필요).

브라우저 탭에서 열면: 관련도순 정렬, 검색, 최소 관련도 필터, 탐색 발견만 보기,
초록 토글. LaTeX 는 MathJax(CDN)로 렌더 — 오프라인이면 원본 $...$ 로 표시된다.
"""
from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path


_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>리서치 다이제스트</title>
<script>
window.MathJax = { tex: { inlineMath: [['$','$']], displayMath: [['$$','$$']] },
  options: { skipHtmlTags: ['script','noscript','style','textarea'] } };
</script>
<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
<style>
  :root{
    --bg:#F6F7F9; --surface:#FFFFFF; --ink:#15161C; --muted:#71727F;
    --line:#E6E7EC; --accent:#4338CA; --accent-soft:#EEECFB;
    --explore:#0D9488; --explore-soft:#E3F4F1;
    --serif: ui-serif, "Iowan Old Style", Georgia, "Times New Roman", serif;
    --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Apple SD Gothic Neo", sans-serif;
    --mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{background:var(--bg);color:var(--ink);font-family:var(--sans);
    font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}

  header{position:sticky;top:0;z-index:5;background:rgba(246,247,249,.85);
    backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
  .bar{max-width:880px;margin:0 auto;padding:18px 20px 14px}
  .eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.14em;
    text-transform:uppercase;color:var(--muted)}
  h1{font-family:var(--serif);font-weight:600;font-size:26px;margin:2px 0 2px;
    letter-spacing:-.01em}
  .sub{color:var(--muted);font-size:13px}
  .controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:14px}
  .controls input[type=search]{flex:1 1 200px;min-width:160px;padding:8px 11px;
    border:1px solid var(--line);border-radius:8px;background:var(--surface);
    font:inherit;color:inherit}
  .controls select,.seg button{font:inherit;color:inherit}
  .controls select{padding:8px 10px;border:1px solid var(--line);border-radius:8px;
    background:var(--surface)}
  .seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
  .seg button{background:var(--surface);border:0;padding:8px 11px;cursor:pointer;
    border-left:1px solid var(--line)}
  .seg button:first-child{border-left:0}
  .seg button[aria-pressed=true]{background:var(--accent);color:#fff}
  label.thr{font-size:13px;color:var(--muted);display:inline-flex;gap:7px;align-items:center}
  label.thr output{font-family:var(--mono);color:var(--ink);min-width:1.4em;text-align:right}

  main{max-width:880px;margin:0 auto;padding:18px 20px 64px}
  .count{font-size:13px;color:var(--muted);margin:2px 0 14px;font-family:var(--mono)}

  .card{position:relative;display:grid;grid-template-columns:64px 1fr;gap:16px;
    background:var(--surface);border:1px solid var(--line);border-radius:12px;
    padding:16px 18px 16px 0;margin-bottom:12px;overflow:hidden}
  /* 시그니처: 왼쪽 관련도 원장 가장자리 */
  .ledger{display:flex;flex-direction:column;align-items:center;justify-content:flex-start;
    padding-top:2px;position:relative}
  .ledger::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
    background:var(--edge,var(--line))}
  .score{font-family:var(--mono);font-size:22px;font-weight:600;line-height:1;
    color:var(--edge,var(--muted))}
  .score small{display:block;font-size:9px;letter-spacing:.1em;color:var(--muted);
    margin-top:4px;font-weight:400}
  .body{min-width:0}
  .title{font-family:var(--serif);font-size:19px;font-weight:600;line-height:1.3;
    margin:0 0 6px;letter-spacing:-.01em}
  .tag{display:inline-block;font-family:var(--mono);font-size:10px;font-weight:600;
    letter-spacing:.06em;color:var(--explore);background:var(--explore-soft);
    padding:2px 7px;border-radius:5px;vertical-align:middle;margin-left:8px}
  .meta{font-size:12.5px;color:var(--muted);margin-bottom:8px}
  .prob{font-family:var(--mono);font-size:10.5px;font-weight:600;color:var(--accent);
    background:var(--accent-soft);padding:1px 7px;border-radius:5px}
  .meta .dot{margin:0 6px;opacity:.5}
  .reason{font-size:13px;color:var(--muted);font-style:italic;margin-bottom:10px}
  .summary{margin:0 0 10px}
  .field{font-size:14px;margin:6px 0}
  .field b{font-family:var(--mono);font-size:11px;letter-spacing:.08em;
    text-transform:uppercase;color:var(--muted);font-weight:600;margin-right:6px}
  .conn{background:var(--accent-soft);border-radius:8px;padding:9px 12px;font-size:14px}
  .chips{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px}
  .chip{font-family:var(--mono);font-size:11px;color:var(--muted);
    border:1px solid var(--line);border-radius:999px;padding:2px 9px}
  .links{margin-top:11px;font-family:var(--mono);font-size:12px;display:flex;gap:14px;
    align-items:center;flex-wrap:wrap}
  .links .id{color:var(--muted)}
  .abstract{margin-top:10px;font-size:13.5px;color:#3a3b47;border-top:1px dashed var(--line);
    padding-top:10px;display:none}
  .abstract.open{display:block}
  .togg{background:none;border:0;color:var(--accent);font:inherit;font-size:12px;
    cursor:pointer;padding:0;font-family:var(--mono)}
  .empty{text-align:center;color:var(--muted);padding:60px 20px}
  :focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  @media (max-width:560px){
    .card{grid-template-columns:48px 1fr;gap:10px;padding-right:14px}
    .title{font-size:17px}
    h1{font-size:22px}
  }
  @media (prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style>
</head>
<body>
<header>
  <div class="bar">
    <div class="eyebrow">arXiv · 리서치 다이제스트</div>
    <h1>%%TITLE%%</h1>
    <div class="sub">갱신 %%GENERATED%% · 총 %%TOTAL%%편</div>
    <div class="controls">
      <input type="search" id="q" placeholder="제목·요약·초록 검색" aria-label="검색">
      <select id="sort" aria-label="정렬">
        <option value="rel">관련도순</option>
        <option value="date">최신순</option>
      </select>
      <select id="prob" aria-label="문제 필터">
        <option value="">전체 문제</option>
      </select>
      <label class="thr">관련도 ≥ <input type="range" id="thr" min="0" max="10" value="0">
        <output id="thrv">0</output></label>
      <span class="seg" role="group" aria-label="필터">
        <button id="fAll" aria-pressed="true">전체</button>
        <button id="fExp" aria-pressed="false">탐색 발견만</button>
      </span>
    </div>
  </div>
</header>
<main>
  <div class="count" id="count"></div>
  <div id="list"></div>
</main>
<script>
const DATA = %%DATA%%;
const PROBLEMS = %%PROBLEMS%%;
const esc = s => (s==null?"":String(s)).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const state = {q:"", sort:"rel", thr:0, exploreOnly:false, problem:""};

function edge(rel, source){
  if(source==="explore") return "var(--explore)";
  if(rel>=8) return "var(--accent)";
  if(rel>=5) return "#8B82DE";
  return "var(--muted)";
}
function fmtDate(iso){ return (iso||"").slice(0,10); }

function card(r){
  const ed = edge(r.relevance, r.source);
  const tag = r.source==="explore" ? '<span class="tag">탐색 발견</span>' : "";
  const authors = (r.authors||[]).slice(0,6).join(", ") + ((r.authors||[]).length>6?" 외":"");
  const cats = (r.categories||[]).join(", ");
  const journal = r.journal_ref ? `<span class="dot">·</span>${esc(r.journal_ref)}` : "";
  const probName = r.problem_name ? `<span class="prob">${esc(r.problem_name)}</span>` : "";
  const meta = `${esc(authors)}<span class="dot">·</span>${esc(cats)}${journal}<span class="dot">·</span>${fmtDate(r.published)}`;
  const tech = r.technique ? `<div class="field"><b>기법</b>${esc(r.technique)}</div>` : "";
  const conn = r.connections ? `<div class="field conn"><b>연결</b>${esc(r.connections)}</div>` : "";
  const chips = (r.keyword_hits||[]).map(k=>`<span class="chip">${esc(k)}</span>`).join("");
  const chipsBox = chips ? `<div class="chips">${chips}</div>` : "";
  const abs = r.abstract ? `<button class="togg" data-id="${esc(r.id)}">초록 보기 ▾</button>
     <div class="abstract" id="abs-${esc(r.id)}">${esc(r.abstract)}</div>` : "";
  return `<article class="card" style="--edge:${ed}">
    <div class="ledger"><div class="score">${r.relevance}<small>/10</small></div></div>
    <div class="body">
      <h2 class="title"><a href="${esc(r.abs_url)}" target="_blank" rel="noopener">${esc(r.title)}</a>${tag}</h2>
      <div class="meta">${probName}${probName?'<span class="dot">·</span>':''}${meta}</div>
      ${r.relevance_reason?`<div class="reason">${esc(r.relevance_reason)}</div>`:""}
      <div class="summary">${esc(r.summary)}</div>
      ${tech}${conn}${chipsBox}
      <div class="links">
        <span class="id">${esc(r.id)}</span>
        <a href="${esc(r.abs_url)}" target="_blank" rel="noopener">abstract ↗</a>
        <a href="${esc(r.pdf_url)}" target="_blank" rel="noopener">pdf ↗</a>
        ${abs?`<span style="flex:1"></span>`:""}
      </div>
      ${abs}
    </div></article>`;
}

function apply(){
  let rows = DATA.slice();
  if(state.problem) rows = rows.filter(r=>r.problem_id===state.problem);
  if(state.exploreOnly) rows = rows.filter(r=>r.source==="explore");
  rows = rows.filter(r=> (r.relevance||0) >= state.thr);
  if(state.q){
    const q = state.q.toLowerCase();
    rows = rows.filter(r => (r.title+" "+r.summary+" "+(r.abstract||"")).toLowerCase().includes(q));
  }
  rows.sort(state.sort==="date"
    ? (a,b)=> (b.published||"").localeCompare(a.published||"")
    : (a,b)=> (b.relevance-a.relevance) || (b.published||"").localeCompare(a.published||""));
  const list = document.getElementById("list");
  document.getElementById("count").textContent = `${rows.length}편 표시`;
  if(!rows.length){ list.innerHTML = `<div class="empty">조건에 맞는 논문이 없습니다. 필터를 낮춰 보세요.</div>`; return; }
  list.innerHTML = rows.map(card).join("");
  if(window.MathJax && MathJax.typesetPromise) MathJax.typesetPromise([list]);
}

document.getElementById("q").addEventListener("input", e=>{state.q=e.target.value; apply();});
document.getElementById("sort").addEventListener("change", e=>{state.sort=e.target.value; apply();});
const probSel=document.getElementById("prob");
PROBLEMS.forEach(p=>{const o=document.createElement("option");o.value=p.id;o.textContent=p.name;probSel.appendChild(o);});
probSel.addEventListener("change", e=>{state.problem=e.target.value; apply();});
const thr=document.getElementById("thr"), thrv=document.getElementById("thrv");
thr.addEventListener("input", e=>{state.thr=+e.target.value; thrv.textContent=e.target.value; apply();});
const fAll=document.getElementById("fAll"), fExp=document.getElementById("fExp");
fAll.addEventListener("click", ()=>{state.exploreOnly=false; fAll.setAttribute("aria-pressed","true"); fExp.setAttribute("aria-pressed","false"); apply();});
fExp.addEventListener("click", ()=>{state.exploreOnly=true; fExp.setAttribute("aria-pressed","true"); fAll.setAttribute("aria-pressed","false"); apply();});
document.getElementById("list").addEventListener("click", e=>{
  const b = e.target.closest(".togg"); if(!b) return;
  const el = document.getElementById("abs-"+b.dataset.id);
  const open = el.classList.toggle("open");
  b.textContent = open ? "초록 숨기기 ▴" : "초록 보기 ▾";
});
apply();
</script>
</body>
</html>"""


def render(records: list[dict], generated_at: dt.datetime, title: str = "관련 논문",
           problems: list | None = None) -> str:
    # 관련도 내림차순 기본 정렬
    rows = sorted(records, key=lambda r: r.get("relevance", 0), reverse=True)
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    probs = problems or []
    probs_json = json.dumps([{"id": p[0], "name": p[1]} for p in probs], ensure_ascii=False)
    return (_TEMPLATE
            .replace("%%DATA%%", data)
            .replace("%%PROBLEMS%%", probs_json.replace("</", "<\\/"))
            .replace("%%TITLE%%", html.escape(title))
            .replace("%%GENERATED%%", generated_at.strftime("%Y-%m-%d %H:%M"))
            .replace("%%TOTAL%%", str(len(rows))))


def write(records: list[dict], out_path: Path, generated_at: dt.datetime,
          title: str = "관련 논문", problems: list | None = None) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(records, generated_at, title, problems), encoding="utf-8")
    return out_path
