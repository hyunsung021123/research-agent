"""누적 코퍼스를 단일 HTML 대시보드로 렌더링(독립 실행, 서버 불필요).

기능: 관련도순/즐겨찾기 우선 정렬, 검색, 최소 관련도, 문제별 필터, 탐색 발견만,
초록 토글, 그리고 즐겨찾기(⭐)·좋아요/싫어요(👍/👎). 피드백은 localStorage 에 즉시
저장되고, GitHub 토큰을 넣으면 data/feedback.json 으로 저장소에 동기화돼 다음
파이프라인 실행이 학습·정리·랭킹에 반영한다. LaTeX 는 MathJax 로 렌더.
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
    --explore:#0D9488; --explore-soft:#E3F4F1; --up:#15803D; --down:#B91C1C;
    --serif: ui-serif, "Iowan Old Style", Georgia, "Times New Roman", serif;
    --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Apple SD Gothic Neo", sans-serif;
    --mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
  }
  *{box-sizing:border-box} html,body{margin:0}
  body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
  a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
  header{position:sticky;top:0;z-index:5;background:rgba(246,247,249,.9);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
  .bar{max-width:880px;margin:0 auto;padding:16px 20px 12px}
  .eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
  h1{font-family:var(--serif);font-weight:600;font-size:25px;margin:2px 0;letter-spacing:-.01em}
  .sub{color:var(--muted);font-size:13px}
  .controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px}
  .controls input[type=search]{flex:1 1 180px;min-width:150px;padding:8px 11px;border:1px solid var(--line);border-radius:8px;background:var(--surface);font:inherit;color:inherit}
  .controls select{padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);font:inherit;color:inherit}
  .seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
  .seg button{background:var(--surface);border:0;padding:8px 11px;cursor:pointer;border-left:1px solid var(--line);font:inherit}
  .seg button:first-child{border-left:0}
  .seg button[aria-pressed=true]{background:var(--accent);color:#fff}
  label.thr{font-size:13px;color:var(--muted);display:inline-flex;gap:7px;align-items:center}
  label.thr output{font-family:var(--mono);color:var(--ink);min-width:1.4em;text-align:right}
  .gear{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:8px 10px;cursor:pointer;font:inherit}
  .panel{max-width:880px;margin:0 auto;padding:0 20px;overflow:hidden;max-height:0;transition:max-height .2s}
  .panel.open{max-height:420px;padding-bottom:12px}
  .panel .box{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px;font-size:13px}
  .panel input{width:100%;padding:7px 9px;border:1px solid var(--line);border-radius:7px;font:inherit;margin:4px 0 10px}
  .panel button{background:var(--accent);color:#fff;border:0;border-radius:7px;padding:8px 14px;cursor:pointer;font:inherit}
  .panel .hint{color:var(--muted);font-size:12px;margin-bottom:8px}
  .refresh-btn{display:inline-flex;align-items:center;gap:6px;background:var(--accent);color:#fff;border:0;border-radius:9px;padding:9px 16px;cursor:pointer;font:inherit;font-size:14px;font-weight:500}
  .refresh-btn:disabled{opacity:.5;cursor:not-allowed}
  .refresh-btn .spin{display:none;width:14px;height:14px;border:2px solid rgba(255,255,255,.4);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite}
  .refresh-btn.loading .spin{display:inline-block}
  @keyframes spin{to{transform:rotate(360deg)}}
  main{max-width:880px;margin:0 auto;padding:14px 20px 64px}
  .count{font-size:13px;color:var(--muted);margin:2px 0 14px;font-family:var(--mono)}
  .card{position:relative;display:grid;grid-template-columns:60px 1fr;gap:16px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px 18px 16px 0;margin-bottom:12px;overflow:hidden}
  .ledger{display:flex;flex-direction:column;align-items:center;padding-top:2px;position:relative}
  .ledger::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--edge,var(--line))}
  .score{font-family:var(--mono);font-size:21px;font-weight:600;line-height:1;color:var(--edge,var(--muted))}
  .score small{display:block;font-size:9px;letter-spacing:.1em;color:var(--muted);margin-top:4px;font-weight:400}
  .body{min-width:0}
  .title{font-family:var(--serif);font-size:19px;font-weight:600;line-height:1.3;margin:0 0 6px;letter-spacing:-.01em}
  .tag{display:inline-block;font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.06em;color:var(--explore);background:var(--explore-soft);padding:2px 7px;border-radius:5px;margin-left:8px}
  .meta{font-size:12.5px;color:var(--muted);margin-bottom:8px}
  .prob{font-family:var(--mono);font-size:10.5px;font-weight:600;color:var(--accent);background:var(--accent-soft);padding:1px 7px;border-radius:5px}
  .meta .dot{margin:0 6px;opacity:.5}
  .reason{font-size:13px;color:var(--muted);font-style:italic;margin-bottom:10px}
  .summary{margin:0 0 10px}
  .field{font-size:14px;margin:6px 0}
  .field b{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600;margin-right:6px}
  .conn{background:var(--accent-soft);border-radius:8px;padding:9px 12px;font-size:14px}
  .chips{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px}
  .chip{font-family:var(--mono);font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:2px 9px}
  .actions{margin-top:11px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .act{border:1px solid var(--line);background:var(--surface);border-radius:8px;padding:5px 10px;cursor:pointer;font:inherit;font-size:13px}
  .act.on-fav{border-color:#D97706;background:#FEF3C7}
  .act.on-up{border-color:var(--up);background:#DCFCE7}
  .act.on-down{border-color:var(--down);background:#FEE2E2}
  .links{margin-left:auto;font-family:var(--mono);font-size:12px;display:flex;gap:14px;align-items:center}
  .links .id{color:var(--muted)}
  .togg{background:none;border:0;color:var(--accent);font:inherit;font-size:12px;cursor:pointer;font-family:var(--mono);margin-top:8px}
  .abstract{margin-top:10px;font-size:13.5px;color:#3a3b47;border-top:1px dashed var(--line);padding-top:10px;display:none}
  .abstract.open{display:block}
  .empty{text-align:center;color:var(--muted);padding:60px 20px}
  .sync{font-family:var(--mono);font-size:11px;color:var(--muted);margin-left:8px}
  :focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  @media (max-width:560px){.card{grid-template-columns:44px 1fr;gap:10px;padding-right:14px}.title{font-size:17px}h1{font-size:21px}.links{margin-left:0;width:100%}}
  @media (prefers-reduced-motion:reduce){*{transition:none}}
</style>
</head>
<body>
<header>
  <div class="bar">
    <div class="eyebrow">arXiv · 리서치 다이제스트</div>
    <h1>%%TITLE%%</h1>
    <div class="sub">갱신 %%GENERATED%% · 총 %%TOTAL%%편 <span class="sync" id="sync"></span></div>
    <div class="controls">
      <button class="refresh-btn" id="refreshBtn">
        <span class="spin"></span>▶ 지금 업데이트
      </button>
      <input type="search" id="q" placeholder="제목·요약·초록 검색" aria-label="검색">
      <select id="sort" aria-label="정렬">
        <option value="fav">즐겨찾기 우선</option>
        <option value="rel">관련도순</option>
        <option value="date">최신순</option>
      </select>
      <select id="prob" aria-label="문제 필터"><option value="">전체 문제</option></select>
      <label class="thr">관련도 ≥ <input type="range" id="thr" min="0" max="10" value="0"><output id="thrv">0</output></label>
      <span class="seg" role="group">
        <button id="fAll" aria-pressed="true">전체</button>
        <button id="fFav" aria-pressed="false">⭐만</button>
        <button id="fExp" aria-pressed="false">탐색만</button>
      </span>
      <span class="seg" role="group"><button id="hideDown" aria-pressed="false">👎 숨기기</button></span>
      <button class="gear" id="gear" title="동기화 설정">⚙</button>
    </div>
  </div>
  <div class="panel" id="panel"><div style="max-width:880px;margin:0 auto"><div class="box">
    <b>GitHub 연동 설정</b>
    <div class="hint">
      토큰 권한: <b>Contents</b>(읽기·쓰기) + <b>Actions</b>(읽기·쓰기) — 두 권한이 있어야
      즐겨찾기·평가 동기화와 수동 업데이트 버튼이 모두 작동합니다.<br>
      fine-grained Personal Access Token 권장. 토큰은 이 기기 브라우저에만 저장됩니다.
    </div>
    <input id="ghRepo" placeholder="owner/repo (예: choihs/research-agent) — 비우면 URL 에서 자동 감지">
    <input id="ghToken" type="password" placeholder="github_pat_... (이 기기에만 저장)">
    <button id="ghSave">저장</button> <span class="sync" id="ghStatus"></span>
  </div></div></div>
</header>
<main>
  <div class="count" id="count"></div>
  <div id="list"></div>
</main>
<script>
const DATA = %%DATA%%;
const PROBLEMS = %%PROBLEMS%%;
const FEEDBACK_REPO = %%FEEDBACK%%;   // 저장소에 커밋된 피드백(기기 간 기준선)
const esc = s => (s==null?"":String(s)).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const baseId = id => String(id).replace(/v\d+$/,"");
const state = {q:"",sort:"fav",thr:0,problem:"",fav:false,exp:false,hideDown:false};

// 피드백 상태: 저장소 기준선 + 로컬 미동기화 병합
let FB = Object.assign({}, FEEDBACK_REPO);
try{ const l = JSON.parse(localStorage.getItem("ra_feedback")||"{}"); Object.assign(FB,l); }catch(e){}
function saveLocal(){ localStorage.setItem("ra_feedback", JSON.stringify(FB)); }

// GitHub 동기화 설정
let GH = {repo:"", token:""};
try{ GH = Object.assign(GH, JSON.parse(localStorage.getItem("ra_gh")||"{}")); }catch(e){}
function autoRepo(){
  if(GH.repo) return GH.repo;
  const h=location.hostname, parts=location.pathname.split("/").filter(Boolean);
  if(h.endsWith("github.io")){ const owner=h.split(".")[0]; return owner+"/"+(parts[0]||h); }
  return "";
}
function setSync(msg){ document.getElementById("sync").textContent = msg; }

async function pushGitHub(){
  const repo = autoRepo(); if(!GH.token || !repo){ return; }
  setSync("동기화 중…");
  const url = `https://api.github.com/repos/${repo}/contents/data/feedback.json`;
  const hdr = {Authorization:`Bearer ${GH.token}`, Accept:"application/vnd.github+json"};
  try{
    let sha = undefined, remote = {};
    const g = await fetch(url, {headers:hdr});
    if(g.status===200){ const j = await g.json(); sha=j.sha;
      try{ remote = JSON.parse(decodeURIComponent(escape(atob(j.content.replace(/\n/g,""))))); }catch(e){} }
    const merged = Object.assign({}, remote, FB);   // 로컬 우선
    const body = { message:"update feedback", content: btoa(unescape(encodeURIComponent(JSON.stringify(merged,null,2)))) };
    if(sha) body.sha = sha;
    const p = await fetch(url, {method:"PUT", headers:hdr, body:JSON.stringify(body)});
    setSync(p.ok ? "동기화됨 ✓" : "동기화 실패("+p.status+")");
  }catch(e){ setSync("동기화 오류"); }
}
let pushTimer=null;
function schedulexPush(){ if(!GH.token) return; clearTimeout(pushTimer); pushTimer=setTimeout(pushGitHub, 1500); }

function setVote(id,v){ const b=baseId(id); const e=FB[b]||{}; e.vote=(e.vote===v?null:v); e.ts=new Date().toISOString(); FB[b]=e; saveLocal(); schedulexPush(); apply(); }
function setFav(id){ const b=baseId(id); const e=FB[b]||{}; e.fav=!e.fav; e.ts=new Date().toISOString(); FB[b]=e; saveLocal(); schedulexPush(); apply(); }

function edge(rel,source){ if(source==="explore")return "var(--explore)"; if(rel>=8)return "var(--accent)"; if(rel>=5)return "#8B82DE"; return "var(--muted)"; }
function fmtDate(iso){ return (iso||"").slice(0,10); }

function card(r){
  const b=baseId(r.id), fb=FB[b]||{};
  const ed=edge(r.relevance,r.source);
  const tag=r.source==="explore"?'<span class="tag">탐색 발견</span>':"";
  const authors=(r.authors||[]).slice(0,6).join(", ")+((r.authors||[]).length>6?" 외":"");
  const journal=r.journal_ref?`<span class="dot">·</span>${esc(r.journal_ref)}`:"";
  const probName=r.problem_name?`<span class="prob">${esc(r.problem_name)}</span><span class="dot">·</span>`:"";
  const tech=r.technique?`<div class="field"><b>기법</b>${esc(r.technique)}</div>`:"";
  const conn=r.connections?`<div class="field conn"><b>연결</b>${esc(r.connections)}</div>`:"";
  const chips=(r.keyword_hits||[]).map(k=>`<span class="chip">${esc(k)}</span>`).join("");
  const abs=r.abstract?`<button class="togg" data-abs="${esc(r.id)}">초록 보기 ▾</button><div class="abstract" id="abs-${esc(r.id)}">${esc(r.abstract)}</div>`:"";
  return `<article class="card" style="--edge:${ed}">
    <div class="ledger"><div class="score">${r.relevance}<small>/10</small></div></div>
    <div class="body">
      <h2 class="title"><a href="${esc(r.abs_url)}" target="_blank" rel="noopener">${esc(r.title)}</a>${tag}</h2>
      <div class="meta">${probName}${esc(authors)}<span class="dot">·</span>${esc((r.categories||[]).join(", "))}${journal}<span class="dot">·</span>${fmtDate(r.published)}</div>
      ${r.relevance_reason?`<div class="reason">${esc(r.relevance_reason)}</div>`:""}
      <div class="summary">${esc(r.summary)}</div>
      ${tech}${conn}${chips?`<div class="chips">${chips}</div>`:""}
      <div class="actions">
        <button class="act ${fb.fav?'on-fav':''}" data-fav="${esc(r.id)}">⭐ 즐겨찾기</button>
        <button class="act ${fb.vote==='up'?'on-up':''}" data-vote="up" data-id="${esc(r.id)}">👍</button>
        <button class="act ${fb.vote==='down'?'on-down':''}" data-vote="down" data-id="${esc(r.id)}">👎</button>
        <span class="links"><span class="id">${esc(r.id)}</span><a href="${esc(r.abs_url)}" target="_blank" rel="noopener">abs ↗</a><a href="${esc(r.pdf_url)}" target="_blank" rel="noopener">pdf ↗</a></span>
      </div>
      ${abs}
    </div></article>`;
}

function apply(){
  let rows=DATA.slice();
  if(state.problem) rows=rows.filter(r=>r.problem_id===state.problem);
  if(state.exp) rows=rows.filter(r=>r.source==="explore");
  if(state.fav) rows=rows.filter(r=>(FB[baseId(r.id)]||{}).fav);
  if(state.hideDown) rows=rows.filter(r=>(FB[baseId(r.id)]||{}).vote!=="down");
  rows=rows.filter(r=>(r.relevance||0)>=state.thr);
  if(state.q){ const q=state.q.toLowerCase(); rows=rows.filter(r=>(r.title+" "+r.summary+" "+(r.abstract||"")).toLowerCase().includes(q)); }
  const favRank=r=>(FB[baseId(r.id)]||{}).fav?1:0;
  rows.sort((a,b)=>{
    if(state.sort==="fav"){ const f=favRank(b)-favRank(a); if(f)return f; }
    if(state.sort==="date") return (b.published||"").localeCompare(a.published||"");
    return (b.relevance-a.relevance)||(b.published||"").localeCompare(a.published||"");
  });
  const list=document.getElementById("list");
  document.getElementById("count").textContent=`${rows.length}편 표시`;
  if(!rows.length){ list.innerHTML=`<div class="empty">조건에 맞는 논문이 없습니다.</div>`; return; }
  list.innerHTML=rows.map(card).join("");
  if(window.MathJax&&MathJax.typesetPromise) MathJax.typesetPromise([list]);
}

// 컨트롤 연결
document.getElementById("q").addEventListener("input",e=>{state.q=e.target.value;apply();});
document.getElementById("sort").addEventListener("change",e=>{state.sort=e.target.value;apply();});
const probSel=document.getElementById("prob");
PROBLEMS.forEach(p=>{const o=document.createElement("option");o.value=p.id;o.textContent=p.name;probSel.appendChild(o);});
probSel.addEventListener("change",e=>{state.problem=e.target.value;apply();});
const thr=document.getElementById("thr"),thrv=document.getElementById("thrv");
thr.addEventListener("input",e=>{state.thr=+e.target.value;thrv.textContent=e.target.value;apply();});
function seg(id,key){const el=document.getElementById(id);el.addEventListener("click",()=>{state[key]=!state[key];el.setAttribute("aria-pressed",String(state[key]));apply();});}
const fAll=document.getElementById("fAll"),fFav=document.getElementById("fFav"),fExp=document.getElementById("fExp");
fAll.addEventListener("click",()=>{state.fav=false;state.exp=false;fAll.setAttribute("aria-pressed","true");fFav.setAttribute("aria-pressed","false");fExp.setAttribute("aria-pressed","false");apply();});
fFav.addEventListener("click",()=>{state.fav=true;state.exp=false;fFav.setAttribute("aria-pressed","true");fAll.setAttribute("aria-pressed","false");fExp.setAttribute("aria-pressed","false");apply();});
fExp.addEventListener("click",()=>{state.exp=true;state.fav=false;fExp.setAttribute("aria-pressed","true");fAll.setAttribute("aria-pressed","false");fFav.setAttribute("aria-pressed","false");apply();});
seg("hideDown","hideDown");

document.getElementById("list").addEventListener("click",e=>{
  const t=e.target.closest("[data-abs],[data-fav],[data-vote]"); if(!t)return;
  if(t.dataset.abs!==undefined){const el=document.getElementById("abs-"+t.dataset.abs);const o=el.classList.toggle("open");t.textContent=o?"초록 숨기기 ▴":"초록 보기 ▾";return;}
  if(t.dataset.fav!==undefined){ setFav(t.dataset.fav); return; }
  if(t.dataset.vote!==undefined){ setVote(t.dataset.id, t.dataset.vote); return; }
});

// 설정 패널
const panel=document.getElementById("panel");
document.getElementById("gear").addEventListener("click",()=>panel.classList.toggle("open"));
document.getElementById("ghRepo").value=GH.repo||"";
document.getElementById("ghToken").value=GH.token||"";
document.getElementById("ghSave").addEventListener("click",async()=>{
  GH.repo=document.getElementById("ghRepo").value.trim();
  GH.token=document.getElementById("ghToken").value.trim();
  localStorage.setItem("ra_gh",JSON.stringify(GH));
  document.getElementById("ghStatus").textContent="저장됨. 동기화 시도…";
  await pushGitHub();
  document.getElementById("ghStatus").textContent=document.getElementById("sync").textContent;
});
setSync(GH.token?("동기화 "+(autoRepo()||"미설정")):"로컬 저장");

// 수동 업데이트 버튼 — GitHub Actions workflow_dispatch 호출
const refreshBtn = document.getElementById("refreshBtn");
async function triggerUpdate(){
  const repo = autoRepo();
  if(!GH.token || !repo){
    alert("⚙ 설정에서 GitHub 저장소와 토큰을 먼저 입력해주세요.\n토큰에 Actions 읽기·쓰기 권한이 필요합니다.");
    return;
  }
  refreshBtn.disabled = true;
  refreshBtn.classList.add("loading");
  refreshBtn.querySelector(".spin").style.display = "inline-block";
  setSync("업데이트 요청 중…");
  try{
    const url = `https://api.github.com/repos/${repo}/actions/workflows/daily.yml/dispatches`;
    const res = await fetch(url, {
      method:"POST",
      headers:{Authorization:`Bearer ${GH.token}`, Accept:"application/vnd.github+json", "Content-Type":"application/json"},
      body: JSON.stringify({ref:"main"})
    });
    if(res.status === 204){
      setSync("⏳ 업데이트 중… (완료되면 자동 새로고침)");
      // workflow_dispatch 후 Actions API 에 run 이 나타날 때까지 잠시 대기
      await new Promise(r=>setTimeout(r, 5000));
      pollUntilDone(repo);
    } else {
      const err = await res.json().catch(()=>({}));
      const msg = err.message || res.status;
      if(res.status === 422) setSync("❌ 이미 실행 중이거나 대기 중");
      else if(res.status === 403) setSync("❌ 권한 없음 — 토큰에 Actions 쓰기 권한 필요");
      else setSync(`❌ 실패 (${msg})`);
    }
  } catch(e){
    setSync("❌ 네트워크 오류");
  } finally {
    setTimeout(()=>{
      refreshBtn.disabled = false;
      refreshBtn.classList.remove("loading");
    }, 10000);
  }
}

// Actions 실행 완료 여부를 10초마다 polling — 완료되면 즉시 새로고침
async function pollUntilDone(repo){
  const hdr = {Authorization:`Bearer ${GH.token}`, Accept:"application/vnd.github+json"};
  const maxWait = 60;  // 최대 10분(60회 × 10초)
  let dots = 0;
  for(let i=0; i<maxWait; i++){
    await new Promise(r=>setTimeout(r, 10000));
    dots = (dots % 3) + 1;
    setSync("⏳ 업데이트 중" + ".".repeat(dots));
    try{
      const r = await fetch(
        `https://api.github.com/repos/${repo}/actions/workflows/daily.yml/runs?per_page=1`,
        {headers: hdr}
      );
      if(!r.ok) continue;
      const data = await r.json();
      const run = (data.workflow_runs||[])[0];
      if(!run) continue;
      if(run.status === "completed"){
        if(run.conclusion === "success"){
          setSync("✅ 완료! 새로고침 중…");
          setTimeout(()=>location.reload(), 1500);
        } else {
          setSync(`❌ 실행 실패 (${run.conclusion})`);
        }
        return;
      }
    } catch(e){ /* 네트워크 일시 오류 무시 */ }
  }
  // 10분 초과 — 그냥 새로고침
  setSync("⏱ 시간 초과, 새로고침 중…");
  setTimeout(()=>location.reload(), 1500);
}
refreshBtn.addEventListener("click", triggerUpdate);
apply();
</script>
</body>
</html>"""


def render(records, generated_at, title="관련 논문", problems=None, feedback=None):
    rows = sorted(records, key=lambda r: r.get("relevance", 0), reverse=True)
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    probs = problems or []
    probs_json = json.dumps([{"id": p[0], "name": p[1]} for p in probs], ensure_ascii=False).replace("</", "<\\/")
    fb_json = json.dumps(feedback or {}, ensure_ascii=False).replace("</", "<\\/")
    return (_TEMPLATE
            .replace("%%DATA%%", data)
            .replace("%%PROBLEMS%%", probs_json)
            .replace("%%FEEDBACK%%", fb_json)
            .replace("%%TITLE%%", html.escape(title))
            .replace("%%GENERATED%%", generated_at.strftime("%Y-%m-%d %H:%M"))
            .replace("%%TOTAL%%", str(len(rows))))


def write(records, out_path: Path, generated_at, title="관련 논문", problems=None, feedback=None):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(records, generated_at, title, problems, feedback), encoding="utf-8")
    return out_path
