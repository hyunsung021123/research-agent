"""보존(정리) 정책 — 누적 논문 수를 통제한다.

규칙(보호된 것은 절대 삭제 안 함):
  보호 = 즐겨찾기(fav) + 좋아요(up)   (protect_favorites 가 True 일 때)
  유지 = 보호 ∪ (최근 keep_days 이내) ∪ (관련도 >= min_relevance)
  keep_top > 0 이면, 위 유지분 중 비보호 항은 관련도 상위 keep_top 편만 남김.
정리된 항은 archive.jsonl 로 옮겨 학습 이력은 보존한다(원하면).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import corpus as corpus_mod
from . import feedback as fb_mod


def _base(r: dict) -> str:
    return corpus_mod.base_id(r.get("id", ""))


def partition(records: list[dict], retention, feedback: dict[str, dict],
              now: dt.datetime) -> tuple[list[dict], list[dict]]:
    """(유지, 정리) 로 분할."""
    cutoff = now - dt.timedelta(days=retention.keep_days)

    def protected(r: dict) -> bool:
        if not retention.protect_favorites:
            return False
        b = _base(r)
        return fb_mod.is_fav(feedback, b) or fb_mod.vote_of(feedback, b) == "up"

    def recent(r: dict) -> bool:
        try:
            return dt.datetime.fromisoformat(r.get("published", "")) >= cutoff
        except Exception:
            return True  # 날짜 파싱 실패 시 보수적으로 유지

    keep, drop = [], []
    for r in records:
        if protected(r) or recent(r) or r.get("relevance", 0) >= retention.min_relevance > 0:
            keep.append(r)
        else:
            drop.append(r)

    # keep_top: 비보호 항만 관련도 상위 N 으로 제한
    if retention.keep_top and retention.keep_top > 0:
        prot = [r for r in keep if protected(r)]
        rest = [r for r in keep if not protected(r)]
        rest.sort(key=lambda r: r.get("relevance", 0), reverse=True)
        cut = rest[retention.keep_top:]
        keep = prot + rest[: retention.keep_top]
        drop += cut
    return keep, drop


def apply_retention(corpus_path: Path, archive_path: Path, retention,
                    feedback: dict[str, dict], now: dt.datetime) -> tuple[int, int]:
    """코퍼스를 정리해 다시 쓴다. (유지 수, 정리 수) 반환."""
    records = _load(corpus_path)
    if not records:
        return (0, 0)
    keep, drop = partition(records, retention, feedback, now)
    if drop and retention.archive:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with open(archive_path, "a", encoding="utf-8") as f:
            for r in drop:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # 코퍼스 재작성(유지분만)
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with open(corpus_path, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return (len(keep), len(drop))


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
