#!/usr/bin/env python3
"""문제별 키워드 추가/제거 후보를 검수 파일로 산출(LLM 호출 없음).

  python learn_keywords.py
"""
from __future__ import annotations

import argparse

from agent.config import load_config
from agent import keyword_learner as kl


def main() -> int:
    ap = argparse.ArgumentParser(description="문제별 키워드 자기학습(제안)")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--high", type=int, default=7)
    ap.add_argument("--low", type=int, default=3)
    args = ap.parse_args()
    cfg = load_config(args.config)
    corpus = kl.load_corpus(cfg.resolve(cfg.paths.corpus))
    if not corpus:
        print("코퍼스가 비었습니다. 먼저 run.py 실행.")
        return 0
    blocks = []
    for prob in cfg.problems:
        recs = [r for r in corpus if r.get("problem_id") == prob.id]
        if not recs:
            continue
        proposals = kl.propose(recs, prob.keywords, high=args.high, low=args.low)
        removals = kl.flag_overbroad(recs, prob.keywords)
        n_pos = sum(1 for r in recs if r.get("relevance", 0) >= args.high)
        n_neg = sum(1 for r in recs if r.get("relevance", 0) <= args.low)
        blocks.append(f"\n\n# 문제: {prob.name} ({prob.id})\n")
        blocks.append(kl.render_review(proposals, removals, len(recs), n_pos, n_neg))
        print(f"[{prob.id}] {len(recs)}편 → 추가후보 {len(proposals)}, 제거후보 {len(removals)}")
    out = cfg.resolve(cfg.paths.corpus).parent / "keyword_review.md"
    out.write_text("".join(blocks), encoding="utf-8")
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
