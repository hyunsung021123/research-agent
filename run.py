#!/usr/bin/env python3
"""AI Research Agent v2 — arXiv 수집 → (다중 문제)평가·요약 → 대시보드/알림.

  python run.py                # config.yaml
  python run.py --dry-run      # LLM 없이 사전필터까지
  python run.py --lookback 14
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import random
import sys

from agent.config import load_config, apply_learned
from agent import arxiv_source, prefilter as pf, summarize, corpus, digest
from agent import keyword_learner as kl, dashboard, notify


def _auto_optimize(cfg, all_records, log):
    """문제별 키워드 학습. 항상 review 파일 생성, auto_apply 면 고신뢰 항 자동 적용."""
    learned_path = cfg.resolve(cfg.paths.learned)
    review_lines = []
    for prob in cfg.problems:
        recs = [r for r in all_records if r.get("problem_id") == prob.id]
        if not recs:
            continue
        proposals = kl.propose(recs, prob.keywords, top=25)
        removals = kl.flag_overbroad(recs, prob.keywords)
        n_pos = sum(1 for r in recs if r.get("relevance", 0) >= 7)
        n_neg = sum(1 for r in recs if r.get("relevance", 0) <= 3)
        review_lines.append(f"\n\n# 문제: {prob.name} ({prob.id})\n")
        review_lines.append(kl.render_review(proposals, removals, len(recs), n_pos, n_neg))
        if cfg.learn.auto_apply:
            picks = [p.term for p in proposals
                     if p.precision >= cfg.learn.min_precision
                     and p.support_pos >= cfg.learn.min_support][: cfg.learn.max_apply_per_run]
            if picks:
                apply_learned(learned_path, prob.id, picks)
                log(f"      [{prob.id}] 키워드 자동 적용: {', '.join(picks)}")
    if review_lines:
        out = learned_path.parent / "keyword_review.md"
        out.write_text("".join(review_lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="arXiv 리서치 에이전트 v2")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--lookback", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    now = dt.datetime.now(dt.timezone.utc)
    state_path = cfg.resolve(cfg.paths.state)
    state = corpus.load_state(state_path)
    seen = corpus.seen_set(state)

    lookback = args.lookback if args.lookback is not None else cfg.arxiv.lookback_days
    since = now - dt.timedelta(days=lookback)

    print(f"[1/4] arXiv 수집: {cfg.arxiv.categories}, since {since.date()} …", flush=True)
    print(f"      문제 {len(cfg.problems)}개: {', '.join(p.id for p in cfg.problems)}", flush=True)
    max_fetch = cfg.arxiv.max_fetch_per_category * len(cfg.arxiv.categories)
    papers = arxiv_source.fetch_recent(cfg.arxiv.categories, since, max_results=max_fetch)
    total_fetched = len(papers)
    fresh = [p for p in papers if corpus.base_id(p.id) not in seen]
    print(f"      {total_fetched}편 수집, 신규 {len(fresh)}편", flush=True)

    print("[2/4] 키워드 사전필터(문제별 배정) …", flush=True)
    scored = pf.prefilter(fresh, cfg.problems)
    candidates = scored[: cfg.llm.max_summarize]
    print(f"      {len(scored)}편 통과, 평가 대상 {len(candidates)}편 (상한 {cfg.llm.max_summarize})", flush=True)

    matched_ids = {s.paper.id for s in scored}
    explore_pool = [p for p in fresh if p.id not in matched_ids]
    n_explore = min(cfg.arxiv.explore_sample, len(explore_pool))
    explore_papers = random.sample(explore_pool, n_explore) if n_explore else []
    if cfg.arxiv.explore_sample:
        print(f"      탐색 대상 {len(explore_papers)}편 (비매칭 {len(explore_pool)}편 중)", flush=True)

    if args.dry_run:
        print("\n[dry-run] 평가 대상:")
        for s in candidates:
            print(f"  [{s.score}] ({s.problem_id}) {s.paper.id}  {s.paper.title}")
        for p in explore_papers:
            print(f"  [탐색] {p.id}  {p.title}")
        return 0

    if not candidates and not explore_papers:
        print("평가할 신규 논문이 없습니다. 종료.")
        corpus.save_state(state_path, now, seen)
        return 0

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("오류: 환경변수 ANTHROPIC_API_KEY 가 설정되지 않았습니다.", file=sys.stderr)
        return 1
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    prob_by_id = {p.id: p for p in cfg.problems}

    print(f"[3/4] Claude 평가·요약 ({cfg.llm.model}) …", flush=True)
    evaluations = []
    for i, s in enumerate(candidates, 1):
        ev = summarize.evaluate(client, s.paper, [prob_by_id[s.problem_id]],
                                cfg.profile.language, cfg.llm.model, cfg.llm.max_tokens,
                                keyword_hits=s.keyword_hits)
        evaluations.append(ev)
        msg = f"ERROR {s.paper.id}: {ev.error[:140]}" if ev.error else f"{ev.relevance}/10 ({ev.problem_id})  {s.paper.id}"
        print(f"      ({i}/{len(candidates)}) {msg}", flush=True)

    if explore_papers:
        print(f"      탐색 평가 ({cfg.llm.explore_model}) …", flush=True)
        for j, p in enumerate(explore_papers, 1):
            ev = summarize.evaluate(client, p, cfg.problems, cfg.profile.language,
                                    cfg.llm.explore_model, cfg.llm.max_tokens,
                                    keyword_hits=[], source="explore")
            evaluations.append(ev)
            msg = f"ERROR {p.id}: {ev.error[:140]}" if ev.error else f"{ev.relevance}/10 ({ev.problem_id})  {p.id}"
            print(f"      [탐색 {j}/{len(explore_papers)}] {msg}", flush=True)

    print("[4/4] 저장·학습·대시보드·알림 …", flush=True)
    run_date = now.date()
    md = digest.render(evaluations, run_date, cfg.llm.relevance_threshold, total_fetched, len(scored))
    out = digest.write_digest(md, cfg.resolve(cfg.paths.digests), run_date)

    records = [e.to_dict() for e in evaluations if e.error is None]
    corpus.append_corpus(cfg.resolve(cfg.paths.corpus), records)
    done_ids = {corpus.base_id(e.paper.id) for e in evaluations if e.error is None}
    corpus.save_state(state_path, now, seen | done_ids)

    all_records = kl.load_corpus(cfg.resolve(cfg.paths.corpus))
    _auto_optimize(cfg, all_records, print)
    dashboard.write(all_records, cfg.resolve(cfg.paths.dashboard), now,
                    problems=[(p.id, p.name) for p in cfg.problems])

    # 알림(이번 실행에서 임계 이상 새 논문)
    fresh_hits = [e for e in evaluations if e.error is None and e.relevance >= cfg.notify.min_relevance]
    notify.maybe_notify(cfg.notify, fresh_hits, run_date)

    n_ok = sum(1 for e in evaluations if e.error is None)
    if evaluations and n_ok == 0:
        print("\n경고: 모든 평가 실패. 위 ERROR 확인 (크레딧/키/모델명). "
              "전체 에러는 다이제스트 하단 참고.")
    kept = sum(1 for e in evaluations if not e.error and e.relevance >= cfg.llm.relevance_threshold)
    print(f"\n완료 → {out}")
    print(f"관련도 {cfg.llm.relevance_threshold}+ {kept}편, 코퍼스 +{len(records)}편")
    print(f"대시보드 → {cfg.resolve(cfg.paths.dashboard)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
