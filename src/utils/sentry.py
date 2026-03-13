"""
Sentry 에러 트래킹 초기화 모듈

무료 플랜 기준:
- 에러 5,000건/월 무료
- 성능 모니터링 비용 없도록 traces_sample_rate=0
- SENTRY_DSN 미설정 시 완전 비활성화
"""

from __future__ import annotations

import sentry_sdk


def init_sentry(dsn: str | None, profile: str = "unknown", release: str | None = None) -> None:
    """Sentry 초기화. dsn이 None이면 아무것도 하지 않음."""
    if not dsn:
        return

    sentry_sdk.init(
        dsn=dsn,
        # 성능 트레이싱 비활성화 (무료 플랜 비용 절감)
        traces_sample_rate=0.0,
        # 프로파일링 비활성화
        profiles_sample_rate=0.0,
        release=release,
        environment=profile,
    )
    sentry_sdk.set_tag("profile", profile)


def capture_exception(exc: BaseException, **extra_tags: str) -> None:
    """예외를 Sentry에 전송. Sentry 미설정이면 무시."""
    if not _is_sentry_enabled():
        return
    with sentry_sdk.push_scope() as scope:
        for key, value in extra_tags.items():
            scope.set_tag(key, value)
        sentry_sdk.capture_exception(exc)


def _is_sentry_enabled() -> bool:
    """Sentry DSN이 설정되어 있는지 확인."""
    return bool(sentry_sdk.Hub.current.client)
