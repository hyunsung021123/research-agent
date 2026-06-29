#!/usr/bin/env python3
"""시드 코퍼스 생성 — 핵심 논문을 미리 평가해 corpus.jsonl 에 넣는다.

arXiv 에 있는 논문은 자동 수집, 없는 것은 메타데이터 직접 기입.
한 번만 실행하면 된다. 이미 corpus 에 있는 논문은 건너뜀.

  python seed.py                # 기본 실행
  python seed.py --dry-run      # API 호출 없이 목록만 확인
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

from agent.config import load_config
from agent.arxiv_source import Paper
from agent import summarize, corpus, keyword_learner as kl

# ── 시드 논문 목록 ─────────────────────────────────────────────────────
SEEDS = [

    # ── McMullen problem — arXiv 있는 논문 ──
    {
        "arxiv_id": "1810.02671",
        "problem_id": "mcmullen",
        "note": "Garcia-Colin, Montejano, Ramirez-Alfonsin 2018",
    },
    {
        "arxiv_id": "1303.3675",
        "problem_id": "mcmullen",
        "note": "Garcia-Colin, Larman 2013: k-neighbourly polytopes",
    },
    {
        "arxiv_id": "2306.00414",
        "problem_id": "mcmullen",
        "note": "k-neighborly reorientations of oriented matroids 2023",
    },
    {
        "arxiv_id": "2606.19573",
        "problem_id": "mcmullen",
        "note": "Embracing exchange sequences and oriented matroid diameter 2026",
    },

    # ── McMullen problem — arXiv 없는 고전 논문 (수동 기입) ──
    {
        "arxiv_id": None,
        "id": "manual-larman1972",
        "problem_id": "mcmullen",
        "title": "On sets projectively equivalent to the vertices of a convex polytope",
        "authors": ["D. G. Larman"],
        "abstract": (
            "We determine the largest number nu(d) such that any nu(d) points in general "
            "position in R^d can be mapped by a permissible projective transformation onto "
            "the vertices of a convex polytope. We prove the lower bound nu(d) >= 2d+1 "
            "using Gale transforms and Radon partitions, establishing Larman's conjecture "
            "that nu(d) = 2d+1. The reformulation via totally cyclic oriented matroids and "
            "acyclic reorientations is central to the proof."
        ),
        "published": "1972-01-01T00:00:00+00:00",
        "journal_ref": "Bull. London Math. Soc. 4 (1972), 6-12",
        "abs_url": "https://doi.org/10.1112/blms/4.1.6",
        "pdf_url": "https://doi.org/10.1112/blms/4.1.6",
        "categories": ["math.CO", "math.MG"],
    },
    {
        "arxiv_id": None,
        "id": "manual-cordovil1985",
        "problem_id": "mcmullen",
        "title": "A problem of McMullen on the projective equivalences of polytopes",
        "authors": ["R. Cordovil", "I. P. da Silva"],
        "abstract": (
            "We give a version for oriented matroids of the McMullen problem: determine "
            "the largest number f(d) such that f(d) points in general position in d-dimensional "
            "real space may be mapped by a permissible projective transformation onto the vertices "
            "of a convex polytope. We prove that for every orientation of the uniform matroid "
            "on 2r-1 elements of rank r with r at least 3, there is an acyclic reorientation "
            "such that all points are extreme points. This recovers the Larman lower bound "
            "f(d) is at least 2d+1 via oriented matroids and chirotopes."
        ),
        "published": "1985-01-01T00:00:00+00:00",
        "journal_ref": "European J. Combin. 6 (1985), 157-161",
        "abs_url": "https://doi.org/10.1016/S0195-6698(85)80006-8",
        "pdf_url": "https://doi.org/10.1016/S0195-6698(85)80006-8",
        "categories": ["math.CO"],
    },
    {
        "arxiv_id": None,
        "id": "manual-ramirez2001",
        "problem_id": "mcmullen",
        "title": (
            "Lawrence oriented matroids and a problem of McMullen "
            "on projective equivalences of polytopes"
        ),
        "authors": ["J. L. Ramirez Alfonsin"],
        "abstract": (
            "We consider the McMullen problem: determine the largest integer f(d) such "
            "that any set of f(d) points in general position in affine d-dimensional space "
            "can be mapped by a projective transformation onto the vertices of a convex polytope. "
            "Using Lawrence oriented matroids, we prove a new upper bound showing that f(d) "
            "is strictly less than 2d plus the ceiling of (d+1)/2, improving the previous "
            "bound of (d+1)(d+2)/2. The technique analyzes acyclic reorientations of "
            "Lawrence oriented matroids and tope structure."
        ),
        "published": "2001-01-01T00:00:00+00:00",
        "journal_ref": "European J. Combin. 22 (2001), 723-731",
        "abs_url": "https://doi.org/10.1006/eujc.2000.0492",
        "pdf_url": "https://doi.org/10.1006/eujc.2000.0492",
        "categories": ["math.CO"],
    },
    {
        "arxiv_id": None,
        "id": "manual-montejano2015",
        "problem_id": "mcmullen",
        "title": "Roudneff's Conjecture for Lawrence Oriented Matroids",
        "authors": ["L. P. Montejano", "J. L. Ramirez Alfonsin"],
        "abstract": (
            "We prove Roudneff's conjecture for Lawrence oriented matroids: every "
            "arrangement of n pseudohyperplanes in projective space P^{d-1} has a cell "
            "meeting all n pseudohyperplanes, provided n >= 2d. This is closely related "
            "to McMullen's problem on convex position of point configurations and the "
            "study of acyclic reorientations. The result gives new bounds on f(d)."
        ),
        "published": "2015-01-01T00:00:00+00:00",
        "journal_ref": "Electron. J. Combin. 22 (2015), P2.3",
        "abs_url": "https://www.combinatorics.org/ojs/index.php/eljc/article/view/v22i2p3",
        "pdf_url": "https://www.combinatorics.org/ojs/index.php/eljc/article/view/v22i2p3",
        "categories": ["math.CO"],
    },

    # ── Polyhedral matching fields — arXiv 있는 논문 ──
    {
        "arxiv_id": "1804.01595",
        "problem_id": "matching-fields",
        "note": "Loho, Smith: Matching fields and lattice points of simplices 2018",
    },
    {
        "arxiv_id": "1809.01026",
        "problem_id": "matching-fields",
        "note": "Mohammadi, Shaw: Toric degenerations of Grassmannians from matching fields 2018",
    },
    {
        "arxiv_id": "2306.09693",
        "problem_id": "matching-fields",
        "note": "Clarke: Matching Fields in Macaulay2 2023",
    },
]


def fetch_arxiv_paper(arxiv_id: str) -> Paper | None:
    try:
        import arxiv
        client = arxiv.Client(delay_seconds=2.0)
        results = list(client.results(arxiv.Search(id_list=[arxiv_id])))
        if not results:
            return None
        r = results[0]
        return Paper(
            id=r.get_short_id(),
            title=r.title.strip().replace("\n", " "),
            authors=[a.name for a in r.authors],
            abstract=r.summary.strip().replace("\n", " "),
            categories=list(r.categories),
            primary_category=r.primary_category,
            published=r.published.isoformat(),
            updated=r.updated.isoformat(),
            abs_url=r.entry_id,
            pdf_url=r.pdf_url,
            journal_ref=r.journal_ref or "",
            doi=r.doi or "",
            comment=r.comment or "",
        )
    except Exception as e:
        print(f"  arXiv 수집 실패 ({arxiv_id}): {e}")
        return None


def manual_paper(s: dict) -> Paper:
    return Paper(
        id=s["id"],
        title=s["title"],
        authors=s["authors"],
        abstract=s["abstract"],
        categories=s.get("categories", ["math.CO"]),
        primary_category=s.get("categories", ["math.CO"])[0],
        published=s.get("published", "2000-01-01T00:00:00+00:00"),
        updated=s.get("published", "2000-01-01T00:00:00+00:00"),
        abs_url=s.get("abs_url", ""),
        pdf_url=s.get("pdf_url", ""),
        journal_ref=s.get("journal_ref", ""),
        doi="",
        comment="",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="시드 코퍼스 생성")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    corpus_path = cfg.resolve(cfg.paths.corpus)
    prob_by_id = {p.id: p for p in cfg.problems}

    # 기존 corpus ID 수집
    existing: set[str] = set()
    if corpus_path.exists():
        for line in corpus_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    r = json.loads(line)
                    existing.add(r.get("id", ""))
                    existing.add(corpus.base_id(r.get("id", "")))
                except Exception:
                    pass

    print(f"시드 논문 {len(SEEDS)}편 | 기존 코퍼스 {len(existing)//2}편\n")

    if args.dry_run:
        print("[dry-run] 평가 예정 목록:")
        for s in SEEDS:
            aid = s.get("arxiv_id")
            sid = aid or s.get("id", "?")
            skip = any(sid in e or (aid and aid in e) for e in existing)
            tag = "SKIP" if skip else "평가"
            label = s.get("note") or s.get("title", "")[:55]
            print(f"  [{tag}] ({s['problem_id']}) {sid[:20]:<20} {label}")
        return 0

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("오류: ANTHROPIC_API_KEY 가 없습니다.", file=sys.stderr)
        return 1

    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)

    records = []
    for i, s in enumerate(SEEDS, 1):
        aid = s.get("arxiv_id")
        sid = aid or s.get("id", "?")

        if any(sid in e or (aid and aid in e) for e in existing):
            print(f"  ({i}/{len(SEEDS)}) SKIP  {sid}")
            continue

        if aid:
            print(f"  ({i}/{len(SEEDS)}) arXiv {aid} …", flush=True)
            paper = fetch_arxiv_paper(aid)
            if not paper:
                continue
            time.sleep(1)
        else:
            print(f"  ({i}/{len(SEEDS)}) 수동  {sid} …", flush=True)
            paper = manual_paper(s)

        prob = prob_by_id.get(s["problem_id"], cfg.problems[0])
        ev = summarize.evaluate(
            client, paper, [prob],
            cfg.profile.language, cfg.llm.model, cfg.llm.max_tokens,
            keyword_hits=[], source="seed",
        )
        if ev.error:
            print(f"    → 평가 실패: {ev.error[:100]}")
            continue

        print(f"    → {ev.relevance}/10  {paper.title[:60]}")
        r = ev.to_dict()
        r["source"] = "seed"
        records.append(r)
        existing.add(paper.id)
        existing.add(corpus.base_id(paper.id))
        time.sleep(0.5)

    if records:
        corpus.append_corpus(corpus_path, records)
        print(f"\n완료: 시드 {len(records)}편 저장 → {corpus_path}")
        print("다음 단계: python learn_keywords.py 로 학습된 키워드 확인")
    else:
        print("\n새로 추가된 시드 없음.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
