#!/usr/bin/env python3
"""수동 보존 정리 — 오래되거나 관련도 낮은 논문을 아카이브로 옮겨 코퍼스를 줄인다.
즐겨찾기·좋아요는 보호된다. config 의 retention 설정을 따른다.

  python prune.py                 # config 설정대로
  python prune.py --keep-days 30  # 이번만 30일로
  python prune.py --keep-top 50   # 비보호 논문 중 관련도 상위 50편만
"""
from __future__ import annotations

import argparse
import datetime as dt

from agent.config import load_config
from agent import feedback as fbmod, retention as ret


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--keep-days", type=int, default=None)
    ap.add_argument("--keep-top", type=int, default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.keep_days is not None:
        cfg.retention.keep_days = args.keep_days
    if args.keep_top is not None:
        cfg.retention.keep_top = args.keep_top
    fb = fbmod.load_feedback(cfg.resolve(cfg.paths.feedback))
    kept, dropped = ret.apply_retention(
        cfg.resolve(cfg.paths.corpus), cfg.resolve(cfg.paths.archive),
        cfg.retention, fb, dt.datetime.now(dt.timezone.utc))
    print(f"정리 완료: 유지 {kept}편 / 아카이브 {dropped}편")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
