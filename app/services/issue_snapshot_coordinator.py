"""
프로젝트·종류(full / bhm)별 Sonar 이슈 동기화 동시성.

단일 uvicorn 프로세스에서 사용자 다수가 동시에 같은 프로젝트를 갱신할 때
중복 Sonar 호출을 막기 위해 asyncio.Lock 을 사용한다.
"""
from __future__ import annotations

import asyncio
from typing import Literal

Kind = Literal["full", "bhm"]

_locks_full: dict[str, asyncio.Lock] = {}
_locks_bhm: dict[str, asyncio.Lock] = {}


def lock_for(project_id: str, kind: Kind) -> asyncio.Lock:
    pid = str(project_id or "").strip()
    d = _locks_full if kind == "full" else _locks_bhm
    if pid not in d:
        d[pid] = asyncio.Lock()
    return d[pid]
