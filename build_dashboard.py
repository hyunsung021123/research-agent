#!/usr/bin/env python3
"""코퍼스 → 대시보드 HTML.  python build_dashboard.py [--min N]"""
from __future__ import annotations

import argparse
import datetime as dt

from agent.config import load_config
from agent import keyword_learner as kl, dashboard, feedback as fbmod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--min", type=int, default=0)
    args = ap.parse_args()
    cfg = load_config(args.config)
    records = [r for r in kl.load_corpus(cfg.resolve(cfg.paths.corpus)) if r.get("relevance", 0) >= args.min]
    if not records:
        print("코퍼스가 비었거나 조건에 맞는 논문이 없습니다.")
        return 0
    fb = fbmod.load_feedback(cfg.resolve(cfg.paths.feedback))
    out = cfg.resolve(cfg.paths.dashboard)
    dashboard.write(records, out, dt.datetime.now(),
                    problems=[(p.id, p.name) for p in cfg.problems], feedback=fb)
    print(f"대시보드 {len(records)}편 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
