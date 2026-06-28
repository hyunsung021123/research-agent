"""Claude 기반 관련도 평가 + 요약 (다중 문제).

논문 하나당 호출 1회. 후보(키워드 매칭)는 배정된 단일 문제로 평가하고,
탐색(explore)은 모든 문제를 주고 LLM 이 가장 맞는 문제를 고르게 한다.
출력(JSON): relevance, problem_id, relevance_reason, summary, technique, connections.

환각 통제: 초록에 명시된 내용만 사용. 불확실하면 표기. 기존 결과를 새 발견처럼 금지.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from anthropic import Anthropic

from .arxiv_source import Paper
from .config import Problem

SYSTEM = """\
당신은 이산기하학·조합론 분야의 시니어 연구자입니다. 연구자를 대신해 arXiv 신규 논문을
평가·요약합니다.

[엄격한 규칙]
1. 초록(abstract)에 명시된 내용만 사용. 없는 정리·수치·방법을 추론/날조 금지.
2. 확신 없으면 "초록만으로는 불확실" 명시.
3. 이미 알려진 결과를 새 발견처럼 서술 금지.
4. relevance 는 아래 '연구 문제'에 대한 직접 관련성으로만. 같은 분야란 이유로 높이지 말 것.
   무관하면 낮게(0-3) 주는 게 정상.
5. 수식은 LaTeX($...$, $$...$$). 출력 언어: {language}(수학 용어는 영어 병기 가능).
6. connections: 초록 근거가 있으면 그대로, 추론이면 "추측:" 접두사, 약하면 빈 문자열.

[연구 문제 후보]
{problems}

problem_id 는 위 목록의 id 중 가장 잘 맞는 하나를 고르십시오."""

USER = """\
제목: {title}
저자: {authors}
분류: {categories}
초록:
{abstract}

아래 JSON 스키마로만 응답(코드펜스·설명 없이 순수 JSON):
{{
  "relevance": <0-10 정수>,
  "problem_id": "<가장 맞는 문제 id>",
  "relevance_reason": "<한 문장>",
  "summary": "<초록 기반 2-3문장>",
  "technique": "<핵심 기법 한 문장, 없으면 빈 문자열>",
  "connections": "<연결 또는 '추측:...', 없으면 빈 문자열>"
}}"""


@dataclass
class Evaluation:
    paper: Paper
    relevance: int
    problem_id: str
    problem_name: str
    relevance_reason: str
    summary: str
    technique: str
    connections: str
    keyword_hits: list[str]
    source: str = "filter"
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = self.paper.to_dict()
        d.update(relevance=self.relevance, problem_id=self.problem_id,
                 problem_name=self.problem_name, relevance_reason=self.relevance_reason,
                 summary=self.summary, technique=self.technique,
                 connections=self.connections, keyword_hits=self.keyword_hits,
                 source=self.source)
        return d


def _parse_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t[3:]
        t = t[4:] if t.lower().startswith("json") else t
        if t.endswith("```"):
            t = t[:-3]
    s, e = t.find("{"), t.rfind("}")
    if s != -1 and e != -1 and e > s:
        t = t[s:e + 1]
    return json.loads(t)


def evaluate(client: Anthropic, paper: Paper, problems: list[Problem],
             language: str, model: str, max_tokens: int,
             keyword_hits: list[str], source: str = "filter") -> Evaluation:
    prob_block = "\n".join(f"- id={p.id} | {p.name}: {p.description.strip()[:400]}"
                           for p in problems)
    name_by_id = {p.id: p.name for p in problems}
    default_pid = problems[0].id
    system = SYSTEM.format(language=language, problems=prob_block)
    user = USER.format(
        title=paper.title,
        authors=", ".join(paper.authors[:8]) + ("…" if len(paper.authors) > 8 else ""),
        categories=", ".join(paper.categories), abstract=paper.abstract)
    try:
        msg = client.messages.create(model=model, max_tokens=max_tokens,
                                     system=system,
                                     messages=[{"role": "user", "content": user}])
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        data = _parse_json(text)
        pid = str(data.get("problem_id", default_pid))
        if pid not in name_by_id:
            pid = default_pid
        rel = max(0, min(10, int(data.get("relevance", 0))))
        return Evaluation(
            paper=paper, relevance=rel, problem_id=pid, problem_name=name_by_id[pid],
            relevance_reason=str(data.get("relevance_reason", "")).strip(),
            summary=str(data.get("summary", "")).strip(),
            technique=str(data.get("technique", "")).strip(),
            connections=str(data.get("connections", "")).strip(),
            keyword_hits=keyword_hits, source=source)
    except Exception as e:
        return Evaluation(
            paper=paper, relevance=0, problem_id=default_pid,
            problem_name=name_by_id.get(default_pid, ""), relevance_reason="",
            summary="", technique="", connections="", keyword_hits=keyword_hits,
            source=source, error=f"{type(e).__name__}: {e}")
