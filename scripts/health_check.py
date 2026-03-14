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
CPU_STEAL_WARN_PCT = 30.0


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
        from src.database.connection import get_db_session_direct, init_db
        init_db(config)
        session = get_db_session_direct()
        try:
            session.execute(__import__("sqlalchemy").text("SELECT 1"))
        finally:
            session.close()
        return True
    except Exception as e:
        get_logger(__name__).error(f"DB 연결 실패: {e}")
        return False


def check_today_collect(config, profile: str) -> int:
    """오늘 수집된 릴스 건수 확인"""
    try:
        from src.database.connection import get_db_session_direct, init_db
        from src.database.models import Reel
        init_db(config)
        import sqlalchemy as sa

        # collected_at은 KST naive datetime으로 저장됨 → KST 기준 오늘 자정과 비교
        from datetime import timedelta
        KST = timezone(timedelta(hours=9))
        today_kst = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        session = get_db_session_direct()
        try:
            count = session.scalar(
                sa.select(sa.func.count()).select_from(Reel).where(
                    Reel.collected_at >= today_kst,
                    Reel.country_code == profile.lower(),
                )
            )
        finally:
            session.close()
        return count or 0
    except Exception as e:
        get_logger(__name__).error(f"수집 건수 조회 실패: {e}")
        return -1


def check_cpu_steal() -> float:
    """CPU steal % 확인 (/proc/stat 2회 측정, 1초 간격)"""
    import time

    def _read_stat() -> list[int]:
        with open("/proc/stat") as f:
            line = f.readline()
        return [int(v) for v in line.split()[1:]]

    try:
        s1 = _read_stat()
        time.sleep(1)
        s2 = _read_stat()
        diff = [b - a for a, b in zip(s1, s2)]
        total = sum(diff)
        steal = diff[7] if len(diff) > 7 else 0
        return steal / total * 100 if total > 0 else 0.0
    except Exception:
        return 0.0


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
    vpn_ok = check_nordvpn(profile)
    if not vpn_ok:
        issues.append("NordVPN 연결 끊김")
        if notifier:
            notifier._post(f"⚠️ *[{profile.upper()}] NordVPN 연결 끊김*\n`nordvpn connect` 수동 실행 필요")

    # 2. DB 연결
    db_ok = check_db(config)
    if not db_ok:
        issues.append("DB 연결 실패")
        if notifier:
            notifier.send_db_error(profile, "헬스체크 DB ping 실패")

    # 3. 오늘 수집 건수
    count = check_today_collect(config, profile)
    if count == 0:
        issues.append("오늘 수집 0건")
        if notifier:
            notifier.send_zero_collect(profile)

    # 4. 디스크 용량
    disk_path = "/srv/insta_scrap" if Path("/srv/insta_scrap").exists() else str(project_root)
    used_pct = check_disk(disk_path)
    if used_pct >= DISK_WARN_PCT:
        issues.append(f"디스크 {used_pct:.1f}%")
        if notifier:
            notifier.send_disk_warning(profile, used_pct)

    # 5. CPU steal (버스트 크레딧 고갈 감지)
    steal_pct = check_cpu_steal()
    if steal_pct >= CPU_STEAL_WARN_PCT:
        issues.append(f"CPU steal {steal_pct:.1f}%")
        if notifier:
            notifier.send_cpu_steal_warning(profile, steal_pct)

    # 매시간 Slack 상태 요약 전송
    from src.utils.notifier import _flag
    status = "🔴 이상" if issues else "🟢 정상"
    detail_lines = [
        f"VPN: {'✅' if vpn_ok else '❌'}",
        f"DB: {'✅' if db_ok else '❌'}",
        f"오늘 수집: {count}건",
        f"디스크: {used_pct:.1f}%",
        f"CPU steal: {steal_pct:.1f}%",
    ]
    if issues:
        detail_lines.append(f"이상: {', '.join(issues)}")
    if notifier:
        notifier._post(
            f"{_flag(profile)} *[{profile.upper()}] 헬스체크 {status}*\n"
            + "\n".join(detail_lines)
        )

    if issues:
        logger.warning(f"[{profile.upper()}] 헬스체크 이상 감지: {', '.join(issues)}")
    else:
        logger.info(f"[{profile.upper()}] 헬스체크 정상")


if __name__ == "__main__":
    main()
