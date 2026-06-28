"""평가 결과를 마크다운 다이제스트로 렌더링."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .summarize import Evaluation


def _badge(rel: int) -> str:
    if rel >= 8:
        return f"🔴 {rel}/10 (높음)"
    if rel >= 5:
        return f"🟡 {rel}/10 (중간)"
    return f"⚪ {rel}/10 (낮음)"


def render(
    evaluations: list[Evaluation],
    run_date: dt.date,
    threshold: int,
    total_fetched: int,
    total_prefiltered: int,
) -> str:
    kept = [e for e in evaluations if e.error is None and e.relevance >= threshold]
    kept.sort(key=lambda e: e.relevance, reverse=True)
    errors = [e for e in evaluations if e.error is not None]

    lines: list[str] = []
    lines.append(f"# arXiv 리서치 다이제스트 — {run_date.isoformat()}")
    lines.append("")
    lines.append(
        f"수집 {total_fetched}편 → 키워드 필터 {total_prefiltered}편 → "
        f"평가 {len(evaluations)}편 → 관련도 {threshold}+ **{len(kept)}편**"
    )
    lines.append("")

    if not kept:
        lines.append("_관련도 임계값을 넘는 신규 논문이 없습니다._")
    for e in kept:
        p = e.paper
        tag = " 💡 탐색 발견(키워드 미매칭)" if e.source == "explore" else ""
        lines.append(f"## {p.title}{tag}")
        lines.append("")
        lines.append(f"**관련도** {_badge(e.relevance)} — {e.relevance_reason}")
        lines.append("")
        authors = ", ".join(p.authors[:6]) + ("…" if len(p.authors) > 6 else "")
        lines.append(f"- 저자: {authors}")
        lines.append(f"- 분류: {', '.join(p.categories)}  ·  제출: {p.published[:10]}")
        lines.append(f"- 링크: [abs]({p.abs_url}) · [pdf]({p.pdf_url}) · `{p.id}`")
        if e.keyword_hits:
            lines.append(f"- 매칭 키워드: {', '.join(e.keyword_hits)}")
        lines.append("")
        lines.append(f"**요약**  {e.summary}")
        lines.append("")
        if e.technique:
            lines.append(f"**핵심 기법**  {e.technique}")
            lines.append("")
        if e.connections:
            lines.append(f"**연결/착안점**  {e.connections}")
            lines.append("")
        lines.append("---")
        lines.append("")

    if errors:
        lines.append(f"### ⚠️ 평가 실패 {len(errors)}편")
        for e in errors:
            lines.append(f"- `{e.paper.id}` {e.paper.title} — {e.error}")
        lines.append("")

    return "\n".join(lines)


def write_digest(text: str, digest_dir: Path, run_date: dt.date) -> Path:
    digest_dir.mkdir(parents=True, exist_ok=True)
    out = digest_dir / f"{run_date.isoformat()}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    return out
