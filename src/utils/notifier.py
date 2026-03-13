"""
Slack 알림 모듈
수집/추적 오류 및 일일 요약을 Slack으로 전송
"""

import json
import urllib.request
from urllib.error import URLError

from src.utils.logger import get_logger

logger = get_logger(__name__)

_COUNTRY_EMOJI = {"kr": "🇰🇷", "jp": "🇯🇵", "us": "🇺🇸"}


def _flag(profile: str) -> str:
    return _COUNTRY_EMOJI.get(profile.lower(), f"[{profile.upper()}]")


class SlackNotifier:
    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    def _post(self, text: str) -> None:
        payload = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            self._url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status != 200:
                    logger.warning(f"Slack 응답 오류: {resp.status}")
        except URLError as e:
            logger.warning(f"Slack 알림 전송 실패: {e}")

    def send_login_error(self, profile: str, detail: str = "") -> None:
        flag = _flag(profile)
        msg = f"{flag} *[{profile.upper()}] 로그인 실패*\n계정 잠금 또는 세션 만료 가능성 있음."
        if detail:
            msg += f"\n```{detail[:200]}```"
        self._post(msg)

    def send_zero_collect(self, profile: str) -> None:
        flag = _flag(profile)
        self._post(
            f"{flag} *[{profile.upper()}] 수집 0건*\nInstagram 차단 또는 계정 문제 의심."
        )

    def send_db_error(self, profile: str, detail: str = "") -> None:
        flag = _flag(profile)
        msg = f"{flag} *[{profile.upper()}] DB 연결 실패*"
        if detail:
            msg += f"\n```{detail[:200]}```"
        self._post(msg)

    def send_s3_error(self, profile: str, fail_count: int) -> None:
        flag = _flag(profile)
        self._post(
            f"{flag} *[{profile.upper()}] S3 업로드 실패 {fail_count}건*\n썸네일 원본 CDN URL로 fallback됨."
        )

    def send_disk_warning(self, profile: str, used_pct: float) -> None:
        flag = _flag(profile)
        self._post(
            f"{flag} *[{profile.upper()}] 디스크 사용률 경고*\n현재 사용률: {used_pct:.1f}% (임계값 70%)"
        )

    def send_summary(self, profile: str, collect_count: int, duration_sec: int) -> None:
        flag = _flag(profile)
        mins = duration_sec // 60
        secs = duration_sec % 60
        self._post(
            f"{flag} *[{profile.upper()}] 수집 완료*\n"
            f"수집 건수: {collect_count}건 | 소요 시간: {mins}분 {secs}초"
        )

    def send_track_summary(self, profile: str, tracked_count: int, duration_sec: int) -> None:
        flag = _flag(profile)
        mins = duration_sec // 60
        secs = duration_sec % 60
        self._post(
            f"{flag} *[{profile.upper()}] 추적 완료*\n"
            f"추적 건수: {tracked_count}건 | 소요 시간: {mins}분 {secs}초"
        )


def get_notifier(config) -> SlackNotifier | None:  # type: ignore[type-arg]
    """config에서 SlackNotifier 반환. webhook_url 없으면 None."""
    url = getattr(config, "slack_webhook_url", None)
    if not url:
        return None
    return SlackNotifier(url)
