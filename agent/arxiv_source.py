"""arXiv API에서 지정 카테고리의 신규 논문을 수집."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, asdict
from typing import Iterable

import arxiv


@dataclass
class Paper:
    id: str            # 예: "2406.01234v1"
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    primary_category: str
    published: str     # ISO
    updated: str       # ISO
    abs_url: str
    pdf_url: str
    journal_ref: str = ""
    doi: str = ""
    comment: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _build_query(categories: list[str]) -> str:
    # (cat:math.CO OR cat:math.MG OR ...) 형태
    return " OR ".join(f"cat:{c}" for c in categories)


def fetch_recent(
    categories: list[str],
    since: dt.datetime,
    max_results: int = 800,
    page_size: int = 100,
) -> list[Paper]:
    """submittedDate 내림차순으로 가져오다가 since 이전이면 중단.

    since: 이 시각(UTC) 이후 제출/갱신된 논문만 반환.
    """
    if since.tzinfo is None:
        since = since.replace(tzinfo=dt.timezone.utc)

    query = _build_query(categories)
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    client = arxiv.Client(page_size=page_size, delay_seconds=3.0, num_retries=3)

    papers: list[Paper] = []
    for r in client.results(search):
        published = r.published  # tz-aware UTC
        if published < since:
            break  # 정렬되어 있으므로 더 볼 필요 없음
        short_id = r.get_short_id()
        papers.append(
            Paper(
                id=short_id,
                title=r.title.strip().replace("\n", " "),
                authors=[a.name for a in r.authors],
                abstract=r.summary.strip().replace("\n", " "),
                categories=list(r.categories),
                primary_category=r.primary_category,
                published=published.isoformat(),
                updated=r.updated.isoformat(),
                abs_url=r.entry_id,
                pdf_url=r.pdf_url,
                journal_ref=r.journal_ref or "",
                doi=r.doi or "",
                comment=r.comment or "",
            )
        )
    return papers
