"""사용자 피드백(좋아요/싫어요/즐겨찾기) 로딩.

대시보드가 GitHub API 로 써넣은 data/feedback.json 을 파이프라인이 읽는다.
형식: { "<base_arxiv_id>": {"vote": "up"|"down"|null, "fav": true|false, "ts": "..."} }
"""
from __future__ import annotations

import json
from pathlib import Path


def load_feedback(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def vote_of(fb: dict[str, dict], base_id: str) -> str | None:
    return (fb.get(base_id) or {}).get("vote")


def is_fav(fb: dict[str, dict], base_id: str) -> bool:
    return bool((fb.get(base_id) or {}).get("fav"))
