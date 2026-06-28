"""코퍼스로부터 키워드 후보를 학습(제안)한다.

핵심 원리 — 판별력(discriminative power):
  좋은 키워드는 "고관련 논문에 자주, 저관련 논문에 드물게" 등장하는 항이다.
  단순 빈출어를 긁어오면 기존 필터를 강화할 뿐(필터 버블) 재현율은 안 오른다.
  코퍼스에 탐색(explore)으로 들어온 비매칭 논문이 있을수록 새 키워드 발견력이 커진다.

안전장치:
  - 제안만 한다. config.yaml 을 자동으로 덮어쓰지 않는다(사람 검수 게이트).
  - 최소 지지도(min_support)로 우연한 1회성 항을 거른다.
  - 과대(over-broad) 기존 키워드도 함께 플래깅한다(매칭은 많은데 평균 관련도 낮음).
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

# 영어 불용어 + 수학 논문 범용어(키워드로 부적절)
STOP = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "with", "by",
    "is", "are", "be", "we", "our", "this", "that", "these", "those", "as", "at",
    "from", "it", "its", "their", "which", "such", "can", "may", "also", "more",
    "than", "into", "over", "under", "between", "each", "any", "all", "some",
    "paper", "show", "shows", "prove", "proof", "result", "results", "theorem",
    "using", "use", "used", "study", "give", "gives", "given", "obtain", "new",
    "case", "cases", "general", "main", "first", "second", "every", "let", "where",
    "if", "then", "when", "well", "two", "three", "one", "set", "sets", "space",
    "spaces", "function", "functions", "number", "numbers", "form", "class",
    "classes", "problem", "problems", "method", "methods", "approach", "via",
    "present", "consider", "introduce", "establish", "denote", "called",
    "appear", "appears", "here", "there", "too", "note", "notes", "mention",
    "mentioned", "recall", "finally", "moreover", "however", "particular",
    "particularly", "respectively", "hence", "thus", "therefore", "namely",
    "indeed", "additionally", "furthermore", "studies", "studied", "provides",
    "provide", "based", "many", "several", "various", "certain", "related",
}


@dataclass
class Proposal:
    term: str
    support_pos: int   # 고관련 논문 중 등장 수
    support_neg: int   # 저관련 논문 중 등장 수
    df_pos: float      # 고관련 등장 비율
    df_neg: float      # 저관련 등장 비율
    precision: float   # df_pos / (df_pos + df_neg)
    score: float       # df_pos * precision (빈도 × 판별력)
    examples: list[str]  # 예시 arXiv id


@dataclass
class Removal:
    keyword: str
    matched: int
    mean_relevance: float


def _terms(text: str, n_max: int = 3) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]+", text.lower())
    words = [w for w in words if len(w) > 2 and w not in STOP]
    grams: set[str] = set()
    for n in range(1, n_max + 1):
        for i in range(len(words) - n + 1):
            grams.add(" ".join(words[i : i + n]))
    return grams


def load_corpus(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def propose(
    corpus: list[dict],
    current_keywords: list[str],
    high: int = 7,
    low: int = 3,
    min_support: int = 2,
    top: int = 25,
) -> list[Proposal]:
    cur = {k.lower() for k in current_keywords}
    pos = [r for r in corpus if r.get("relevance", 0) >= high]
    neg = [r for r in corpus if r.get("relevance", 0) <= low]
    npos, nneg = max(1, len(pos)), max(1, len(neg))

    pos_df: Counter[str] = Counter()
    neg_df: Counter[str] = Counter()
    examples: defaultdict[str, list[str]] = defaultdict(list)
    for r in pos:
        text = f"{r.get('title','')} {r.get('abstract','')}"
        for t in _terms(text):
            pos_df[t] += 1
            if len(examples[t]) < 3:
                examples[t].append(r.get("id", "?"))
    for r in neg:
        text = f"{r.get('title','')} {r.get('abstract','')}"
        for t in _terms(text):
            neg_df[t] += 1

    proposals: list[Proposal] = []
    for term, c in pos_df.items():
        if c < min_support or term in cur:
            continue
        # 이미 있는 키워드의 부분/상위 문자열이면 중복으로 보고 제외
        if any(term in k or k in term for k in cur):
            continue
        dfp = c / npos
        dfn = neg_df.get(term, 0) / nneg
        precision = dfp / (dfp + dfn + 1e-9)
        score = dfp * precision
        proposals.append(
            Proposal(
                term=term, support_pos=c, support_neg=neg_df.get(term, 0),
                df_pos=round(dfp, 3), df_neg=round(dfn, 3),
                precision=round(precision, 3), score=round(score, 4),
                examples=examples[term],
            )
        )
    proposals.sort(key=lambda p: p.score, reverse=True)
    proposals = _suppress_subgrams(proposals)
    return proposals[:top]


def _suppress_subgrams(proposals: list[Proposal]) -> list[Proposal]:
    """더 긴 항과 토큰 집합이 포함관계이고 고관련 지지도가 같으면 짧은 쪽 제거.

    예: 'signed'(6) ⊂ 'signed circuit'(6) → 'signed' 제거(더 구체적인 쪽 유지).
    'matroids'(12)는 'matroids tope'(5)와 지지도가 달라 유지된다.
    """
    toks = {p.term: set(p.term.split()) for p in proposals}
    longer_first = sorted(proposals, key=lambda p: len(toks[p.term]), reverse=True)
    drop: set[str] = set()
    for i, a in enumerate(longer_first):
        for b in longer_first[i + 1:]:  # b 는 a 보다 같거나 짧음
            if b.term in drop:
                continue
            if toks[b.term] < toks[a.term] and b.support_pos == a.support_pos:
                drop.add(b.term)
    return [p for p in proposals if p.term not in drop]


def flag_overbroad(
    corpus: list[dict],
    current_keywords: list[str],
    min_matched: int = 4,
    max_mean_relevance: float = 3.5,
) -> list[Removal]:
    """매칭은 많은데 평균 관련도가 낮은 기존 키워드를 제거 후보로 플래깅."""
    by_kw: defaultdict[str, list[int]] = defaultdict(list)
    for r in corpus:
        rel = r.get("relevance", 0)
        for k in r.get("keyword_hits", []):
            by_kw[k].append(rel)
    out: list[Removal] = []
    for k in current_keywords:
        rels = by_kw.get(k.lower(), [])
        if len(rels) >= min_matched:
            mean = sum(rels) / len(rels)
            if mean <= max_mean_relevance:
                out.append(Removal(keyword=k, matched=len(rels), mean_relevance=round(mean, 2)))
    out.sort(key=lambda r: r.mean_relevance)
    return out


def llm_refine(client, model: str, proposals: list[Proposal], profile_text: str,
               max_keep: int = 15) -> list[str]:
    """원시 후보를 Claude로 정제 — 일반어·문장조각·중복을 걸러 진짜 수학 용어만 반환.

    실패 시 빈 리스트(호출자가 원시 후보로 폴백)."""
    import json as _json
    terms = [p.term for p in proposals]
    if not terms:
        return []
    sys = ("당신은 이산기하학·조합론 연구자입니다. 자동 추출된 키워드 후보 중 "
           "이 연구자의 논문 검색 필터로 쓸 만한 '구체적 수학 기술 용어'만 선별합니다. "
           "일반 영어 단어, 문장 조각, 의미 없는 n-gram 조합, 서로 중복되는 항은 제외하세요.")
    user = (f"[연구자 프로필]\n{profile_text}\n\n[후보 목록]\n" + ", ".join(terms) +
            f"\n\n위에서 검색 필터로 적합한 용어만 최대 {max_keep}개, 정규화된 형태로 "
            "JSON 문자열 배열로만 반환하세요. 코드펜스·설명 없이 순수 JSON 배열만.")
    try:
        msg = client.messages.create(
            model=model, max_tokens=600, system=sys,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
        s, e = text.find("["), text.rfind("]")
        arr = _json.loads(text[s : e + 1]) if s != -1 and e != -1 else []
        return [str(x).strip() for x in arr if str(x).strip()][:max_keep]
    except Exception:
        return []


def render_review(
    proposals: list[Proposal],
    removals: list[Removal],
    corpus_size: int,
    n_pos: int,
    n_neg: int,
    refined: list[str] | None = None,
) -> str:
    L: list[str] = []
    L.append("# 키워드 검수 제안")
    L.append("")
    L.append(f"코퍼스 {corpus_size}편 (고관련 {n_pos} / 저관련 {n_neg}) 기준. "
             "아래는 **제안**이며 config는 자동 변경되지 않습니다.")
    L.append("")
    if refined:
        L.append("## ✅ LLM 정제 결과 (바로 검토용)")
        L.append("")
        L.append("```yaml")
        for t in refined:
            L.append(f'    - "{t}"')
        L.append("```")
        L.append("")
    L.append("## 추가 후보 (판별력 순)")
    L.append("")
    if not proposals:
        L.append("_충분한 데이터가 쌓이면 후보가 나타납니다. 탐색(explore_sample)을 켜면 더 빨라집니다._")
    else:
        L.append("| 항(term) | score | 고관련 | 저관련 | precision | 예시 |")
        L.append("|---|---|---|---|---|---|")
        for p in proposals:
            ex = ", ".join(p.examples)
            L.append(f"| `{p.term}` | {p.score} | {p.support_pos} ({p.df_pos}) | "
                     f"{p.support_neg} ({p.df_neg}) | {p.precision} | {ex} |")
        L.append("")
        L.append("승인할 항을 골라 config.yaml 의 `arxiv.keywords` 에 복사:")
        L.append("```yaml")
        for p in proposals[:12]:
            L.append(f'    - "{p.term}"')
        L.append("```")
    L.append("")
    L.append("## 제거 후보 (매칭 多, 평균 관련도 低 — 필터를 넓히기만 함)")
    L.append("")
    if not removals:
        L.append("_없음._")
    else:
        L.append("| 키워드 | 매칭 수 | 평균 관련도 |")
        L.append("|---|---|---|")
        for r in removals:
            L.append(f"| `{r.keyword}` | {r.matched} | {r.mean_relevance} |")
    L.append("")
    return "\n".join(L)
