"""
헬스체크 스크립트
매시간 cron으로 실행 — NordVPN, DB, 수집 건수, 디스크 용량 확인

실행:
  poetry run python scripts/health_check.py --profile kr
"""

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.profile_loader import load_profile
from src.utils.logger import get_logger, setup_logger
from src.utils.notifier import get_notifier

DISK_WARN_PCT = 70.0


def check_nordvpn(profile: str) -> bool:
    """NordVPN 연결 상태 확인"""
    try:
        result = subprocess.run(
            ["nordvpn", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout.lower()
        connected = "connected" in output
        if not connected:
            get_logger(__name__).warning(f"[{profile.upper()}] NordVPN 연결 끊김: {result.stdout.strip()}")
        return connected
    except (FileNotFoundError, subprocess.TimeoutExpired):
        get_logger(__name__).warning(f"[{profile.upper()}] nordvpn 명령 실행 실패 (설치 확인 필요)")
        return True  # 로컬 환경에서는 nordvpn 없어도 경고만


def check_db(config) -> bool:  # type: ignore[type-arg]
    """DB 연결 확인"""
    try:
        from src.database.connection import get_session
        with get_session() as session:
            session.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except Exception as e:
        get_logger(__name__).error(f"DB 연결 실패: {e}")
        return False


def check_today_collect(config, profile: str) -> int:
    """오늘 수집된 릴스 건수 확인"""
    try:
        from src.database.connection import get_session
        from src.database.models import Reel
        import sqlalchemy as sa

        today = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        with get_session() as session:
            count = session.scalar(
                sa.select(sa.func.count()).select_from(Reel).where(
                    Reel.created_at >= today,
                    Reel.country_code == profile.lower(),
                )
            )
        return count or 0
    except Exception as e:
        get_logger(__name__).error(f"수집 건수 조회 실패: {e}")
        return -1


def check_disk(base_path: str = "/srv/insta_scrap") -> float:
    """디스크 사용률(%) 반환"""
    total, used, _ = shutil.disk_usage(base_path)
    return used / total * 100


def main() -> None:
    parser = argparse.ArgumentParser(description="헬스체크")
    parser.add_argument("--profile", "-p", default="kr", help="프로파일 (kr/jp/us)")
    args = parser.parse_args()

    config = load_profile(args.profile)
    setup_logger(log_level="INFO")
    logger = get_logger(__name__)
    notifier = get_notifier(config)

    profile = args.profile
    issues = []

    logger.info(f"[{profile.upper()}] 헬스체크 시작")

    # 1. NordVPN
    if not check_nordvpn(profile):
        issues.append("NordVPN 연결 끊김")
        if notifier:
            notifier._post(f"⚠️ *[{profile.upper()}] NordVPN 연결 끊김*\n`nordvpn connect` 수동 실행 필요")

    # 2. DB 연결
    if not check_db(config):
        issues.append("DB 연결 실패")
        if notifier:
            notifier.send_db_error(profile, "헬스체크 DB ping 실패")

    # 3. 오늘 수집 건수 (cron 수집 시간 이후인 03:00 UTC+ 이후에만 의미 있음)
    now_hour = datetime.now(tz=timezone.utc).hour
    if now_hour >= 3:  # 한국 기준 12시 이후
        count = check_today_collect(config, profile)
        if count == 0:
            issues.append("오늘 수집 0건")
            if notifier:
                notifier.send_zero_collect(profile)
        elif count > 0:
            logger.info(f"[{profile.upper()}] 오늘 수집 건수: {count}건")

    # 4. 디스크 용량
    disk_path = "/srv/insta_scrap" if Path("/srv/insta_scrap").exists() else str(project_root)
    used_pct = check_disk(disk_path)
    logger.info(f"[{profile.upper()}] 디스크 사용률: {used_pct:.1f}%")
    if used_pct >= DISK_WARN_PCT:
        issues.append(f"디스크 {used_pct:.1f}%")
        if notifier:
            notifier.send_disk_warning(profile, used_pct)

    if issues:
        logger.warning(f"[{profile.upper()}] 헬스체크 이상 감지: {', '.join(issues)}")
    else:
        logger.info(f"[{profile.upper()}] 헬스체크 정상")


if __name__ == "__main__":
    main()
