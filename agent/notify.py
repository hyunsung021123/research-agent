"""푸시 알림 (ntfy.sh).

ntfy 는 계정 없이 토픽 URL 하나로 폰/PC 에 푸시를 보내는 무료 서비스다.
폰에 ntfy 앱 설치 후 같은 토픽을 구독하면, 아침마다 상위 논문이 푸시로 뜬다.
토픽 이름은 추측하기 어렵게(예: ra-choihs-x7k2q) 정해야 아무나 못 본다.

확장 지점: 다른 채널(텔레그램, 이메일, 웹푸시)을 추가하려면 send_* 함수를 늘리고
maybe_notify 에서 분기하면 된다.
"""
from __future__ import annotations

import datetime as dt
import urllib.request


def _send_ntfy(server: str, topic: str, title: str, body: str, click: str = "") -> None:
    url = f"{server.rstrip('/')}/{topic}"
    headers = {"Title": title.encode("utf-8")}
    if click:
        headers["Click"] = click
    req = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
    urllib.request.urlopen(req, timeout=15)


def maybe_notify(notify_cfg, evaluations: list, run_date: dt.date) -> None:
    """임계 이상 논문이 있으면 요약 푸시를 보낸다. 설정 꺼져 있으면 아무것도 안 함."""
    if not getattr(notify_cfg, "enabled", False) or not notify_cfg.ntfy_topic:
        return
    if not evaluations:
        return
    top = sorted(evaluations, key=lambda e: e.relevance, reverse=True)[:5]
    lines = [f"[{e.relevance}/10] {e.paper.title}" for e in top]
    body = "\n".join(lines)
    title = f"오늘의 논문 {len(evaluations)}편 ({run_date.isoformat()})"
    try:
        _send_ntfy(notify_cfg.ntfy_server, notify_cfg.ntfy_topic, title, body,
                   click=top[0].paper.abs_url if top else "")
        print(f"      알림 전송: ntfy/{notify_cfg.ntfy_topic} ({len(evaluations)}편)")
    except Exception as e:
        print(f"      알림 실패(무시): {type(e).__name__}: {e}")
