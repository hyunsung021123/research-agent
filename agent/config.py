"""설정 로딩 (v2: 다중 문제 지원) + v1 자동 변환.

문제(problem)별로 keywords/description 을 따로 둔다. 사람이 손보는 config.yaml 과,
기계가 자동 학습한 키워드(data/learned_keywords.json)를 분리해 — 자동 최적화가
사람 파일을 덮어쓰지 않는다. 로드 시 둘을 합쳐 effective keywords 로 쓴다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


def _mk(cls, data: dict | None):
    """dataclass 를 dict 로 생성하되, 정의되지 않은 키는 무시(전/후방 호환)."""
    data = data or {}
    allowed = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in allowed})


@dataclass
class Profile:
    name: str = "researcher"
    language: str = "ko"


@dataclass
class Problem:
    id: str
    name: str
    description: str = ""
    keywords: list[str] = field(default_factory=list)        # 사람 + 학습 합본(effective)
    base_keywords: list[str] = field(default_factory=list)   # 사람이 쓴 것만
    learned_keywords: list[str] = field(default_factory=list)  # 자동 학습된 것만
    exclude_keywords: list[str] = field(default_factory=list)  # 매칭 시 후보에서 제외


@dataclass
class ArxivConfig:
    categories: list[str] = field(default_factory=lambda: ["math.CO", "math.MG"])
    core_categories: list[str] = field(default_factory=list)  # 탐색을 이 카테고리로 제한(빈값=제한없음)
    lookback_days: int = 7
    max_fetch_per_category: int = 200
    explore_sample: int = 8


@dataclass
class LLMConfig:
    model: str = "claude-sonnet-4-6"
    explore_model: str = "claude-haiku-4-5-20251001"
    relevance_threshold: int = 5
    max_summarize: int = 40
    max_tokens: int = 1500


@dataclass
class LearnConfig:
    auto_apply: bool = False     # 자동으로 학습 키워드 적용할지(기본 끔)
    min_precision: float = 0.85  # 자동 적용 최소 판별력
    min_support: int = 3         # 자동 적용 최소 고관련 등장 수
    max_apply_per_run: int = 3   # 1회 실행당 자동 적용 상한(문제별)


@dataclass
class NotifyConfig:
    enabled: bool = False
    ntfy_topic: str = ""                    # 예: "ra-choihs-x7k2q" (추측 어렵게)
    ntfy_server: str = "https://ntfy.sh"
    min_relevance: int = 7                  # 이 점수 이상만 알림


@dataclass
class RetentionConfig:
    keep_days: int = 90        # 이 일수보다 오래된(제출일 기준) 논문은 정리 대상
    keep_top: int = 0          # >0 이면 비보호 논문 중 관련도 상위 N편만 유지
    min_relevance: int = 0     # 이 미만 관련도는 정리 대상(0=끔)
    protect_favorites: bool = True   # 즐겨찾기·좋아요는 절대 삭제 안 함
    archive: bool = True       # 정리된 논문을 archive.jsonl 로 보관(학습 이력 유지)


@dataclass
class Paths:
    corpus: str = "data/corpus.jsonl"
    state: str = "data/state.json"
    learned: str = "data/learned_keywords.json"
    feedback: str = "data/feedback.json"
    archive: str = "data/archive.jsonl"
    digests: str = "digests"
    dashboard: str = "docs/index.html"      # GitHub Pages 가 docs/ 를 서빙


@dataclass
class Config:
    profile: Profile
    problems: list[Problem]
    arxiv: ArxivConfig
    llm: LLMConfig
    learn: LearnConfig
    notify: NotifyConfig
    retention: RetentionConfig
    paths: Paths
    root: Path

    def resolve(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else (self.root / p)


def _load_learned(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _build_problems(raw: dict, learned: dict[str, list[str]]) -> list[Problem]:
    problems_raw = raw.get("problems")
    if not problems_raw:
        # v1 자동 변환: profile.description + arxiv.keywords 를 단일 문제로
        prof = raw.get("profile") or {}
        kws = (raw.get("arxiv") or {}).get("keywords", [])
        problems_raw = [{
            "id": "default",
            "name": "연구 주제",
            "description": prof.get("description", ""),
            "keywords": kws,
        }]
    out: list[Problem] = []
    for p in problems_raw:
        pid = p["id"]
        base = list(p.get("keywords", []))
        learn = list(learned.get(pid, []))
        eff = list(dict.fromkeys(base + learn))  # 순서 보존 dedup
        out.append(Problem(id=pid, name=p.get("name", pid),
                           description=p.get("description", ""),
                           keywords=eff, base_keywords=base, learned_keywords=learn,
                           exclude_keywords=list(p.get("exclude_keywords", []))))
    return out


def load_config(path: str | Path) -> Config:
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {path}")
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    root = path.parent

    paths = _mk(Paths, raw.get("paths"))
    learned_path = (root / paths.learned if not Path(paths.learned).is_absolute()
                    else Path(paths.learned))
    learned = _load_learned(learned_path)

    return Config(
        profile=_mk(Profile, raw.get("profile")),
        problems=_build_problems(raw, learned),
        arxiv=_mk(ArxivConfig, raw.get("arxiv")),
        llm=_mk(LLMConfig, raw.get("llm")),
        learn=_mk(LearnConfig, raw.get("learn")),
        notify=_mk(NotifyConfig, raw.get("notify")),
        retention=_mk(RetentionConfig, raw.get("retention")),
        paths=paths,
        root=root,
    )


def apply_learned(path: Path, problem_id: str, new_keywords: list[str]) -> None:
    """학습된 키워드를 기계 소유 파일에 추가(사람의 config.yaml 은 건드리지 않음)."""
    learned = _load_learned(path)
    cur = learned.get(problem_id, [])
    learned[problem_id] = list(dict.fromkeys(cur + new_keywords))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(learned, ensure_ascii=False, indent=2), encoding="utf-8")
