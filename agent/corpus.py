"""실행 상태와 누적 코퍼스 저장.

- state.json: 마지막 실행 시각, 이미 처리한 논문 id 집합
- corpus.jsonl: 평가된 논문 1건당 1줄(JSON). v2 벡터 검색 층의 입력이 된다.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Iterable


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"last_run": None, "seen_ids": []}
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    d.setdefault("last_run", None)
    d.setdefault("seen_ids", [])
    return d


def save_state(path: Path, last_run: dt.datetime, seen_ids: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"last_run": last_run.isoformat(), "seen_ids": sorted(set(seen_ids))},
            f, ensure_ascii=False, indent=2,
        )


def seen_set(state: dict) -> set[str]:
    return set(state.get("seen_ids", []))


def base_id(arxiv_id: str) -> str:
    """버전 접미사만 제거: 2406.01234v2 -> 2406.01234 (다른 'v' 는 보존)."""
    return re.sub(r"v\d+$", "", arxiv_id or "")


def append_corpus(path: Path, records: list[dict]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
