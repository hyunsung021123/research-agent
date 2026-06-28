"""키워드 1차 필터 (다중 문제). 각 논문을 가장 잘 맞는 문제에 배정한다.

논문은 문제별 키워드 매칭 수를 비교해 최다 매칭 문제 하나에 배정된다(동점이면 첫 문제).
한 논문이 여러 문제에 걸쳐도 가장 강한 한 문제로만 평가한다(비용·단순성). LLM 호출 전
후보를 줄여 비용·노이즈를 통제한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .arxiv_source import Paper
from .config import Problem


@dataclass
class Scored:
    paper: Paper
    problem_id: str
    problem_name: str
    keyword_hits: list[str]

    @property
    def score(self) -> int:
        return len(self.keyword_hits)


def _hits(paper: Paper, keywords: list[str]) -> list[str]:
    hay = f"{paper.title}\n{paper.abstract}".lower()
    return sorted({k for k in (kw.lower() for kw in keywords if kw.strip()) if k in hay})


def prefilter(papers: list[Paper], problems: list[Problem]) -> list[Scored]:
    out: list[Scored] = []
    for p in papers:
        best: Scored | None = None
        for prob in problems:
            hits = _hits(p, prob.keywords)
            if hits and (best is None or len(hits) > len(best.keyword_hits)):
                best = Scored(paper=p, problem_id=prob.id, problem_name=prob.name,
                             keyword_hits=hits)
        if best:
            out.append(best)
    out.sort(key=lambda s: (s.score, s.paper.published), reverse=True)
    return out
